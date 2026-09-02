# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import datetime
from typing import cast

from airflow.sdk import DAG, Param, Variable, dag, task
from pinta_common import constants
from pinta_db.job_db.models.user import DemPreview
from pinta_db.job_db.schema import Schema
from pinta_db.primary_db.models.dem import Dem as PrimaryDem
from pinta_db.primary_db.schema import Schema as PrimarySchema

from pinta_dags import config
from pinta_dags.config import AirflowVariable
from pinta_dags.tasks import (
    build_job_connection_uri_task,
    delete_restore_area,
    find_dirty_update_areas,
    find_restore_areas,
    get_database_name,
    restore_update_area_write_access,
    revoke_update_area_write_access,
    set_processing_status_completed,
    set_processing_status_failed,
    set_processing_status_started,
)

FROM_DB_SCHEMA = PrimarySchema.DEM.value
FROM_DB_TABLE = PrimaryDem.__tablename__
TO_DB_SCHEMA = Schema.USER.value
TO_DB_TABLE = DemPreview.__tablename__


def _get_max_parallel_pipelines() -> int:
    var = AirflowVariable.DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def create_dissolve_update_areas_dag(  # noqa: C901, PLR0915
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Dissolve update areas",
        schedule=None,
        params={
            "id": Param(
                "",
                type="string",
                format="uuid",
                description=("Production area id as UUID"),
            ),
            "restore_write_access": Param(
                default=True,
                type="boolean",
                description=(
                    "Restore the QGIS editors' update_area write access at the "
                    "end. A triggering parent DAG sets this to false to keep "
                    "the editors locked out until its own end."
                ),
            ),
        },
        is_paused_upon_creation=False,
    )
    def dissolve_update_areas_dag() -> None:  # noqa: C901, PLR0915
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task
        def should_restore_write_access(params: dict) -> bool:
            # Read the param in a task so the restore gets a native bool
            # instead of a rendered template string.
            return bool(params["restore_write_access"])

        @task.docker(
            # Parallel tasks can race to insert the same shared overview tile;
            # the spatial uniqueness constraint fails the loser, and a retry
            # then sees the tile in place and skips it.
            **{
                **config.PINTA_CONTAINER_TASK_ARGS,
                "retries": 3,
                "retry_delay": datetime.timedelta(seconds=10),
            },
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def ensure_dem_preview_coverage(
            primary_connection_uri: str,
            job_connection_uri: str,
            update_area_id: str,
        ) -> None:
            """Make sure dem_preview has all required raster tiles.

            If update area spans outside of production area (e.g. waterbody) we need to
            copy missing tiles to dem preview for the dissolve to work. Fully missing
            tiles are inserted as new rows. Tiles at the production area boundary
            exist but are padded by nodata outside of production area. This is a no-op
            if the tiles are already fully populated.
            """
            import sqlalchemy
            import sqlmodel
            from pinta_common import Settings
            from pinta_db.job_db.models.user import DemPreview, UpdateArea
            from pinta_db.primary_db.models.dem import Dem
            from pinta_db_utils import model_utils
            from pinta_db_utils.postgis import raster
            from pinta_processing import pipelines, reader, writer
            from pinta_processing.utils import tiles
            from shapely import wkt as shapely_wkt

            levels = (1, *raster.DEFAULT_OVERVIEW_LEVELS)

            def tables_at_levels(table_name: str) -> list[str]:
                return [
                    table_name
                    if level == 1
                    else raster.OVERVIEW_TABLE_NAME.format(
                        level=level, table_name=table_name
                    )
                    for level in levels
                ]

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                update_area = job_session.exec(
                    sqlmodel.select(UpdateArea).where(UpdateArea.id == update_area_id)
                ).first()
                if update_area is None:
                    # The area was deleted after it was listed
                    return

                geom = shapely_wkt.loads(update_area.geom_wkt)
                footprint = geom.buffer(pipelines.DISSOLVE_PRIMARY_DEM_BUFFER)
                dem_schema, dem_table = model_utils.schema_and_table(Dem)
                preview_schema, preview_table = model_utils.schema_and_table(DemPreview)

                for level, source_table, target_table in zip(
                    levels,
                    tables_at_levels(dem_table),
                    tables_at_levels(preview_table),
                    strict=True,
                ):
                    envelopes = tiles.tile_envelopes(
                        footprint,
                        pixel_size=float(Settings.DB_DEM_PIXEL_SIZE) * level,
                        tile_size=Settings.DB_DEFAULT_TILE_SIZE,
                    )
                    for envelope in envelopes:
                        if tiles.tile_exists(
                            job_session,
                            preview_schema,
                            target_table,
                            envelope,
                            mode=tiles.TileExistsMode.ALL_PIXELS_HAVE_DATA,
                        ):
                            continue
                        if not tiles.tile_exists(
                            primary_session, dem_schema, source_table, envelope
                        ):
                            msg = (
                                f"Update area {update_area_id} cannot be "
                                f"processed: tile {envelope.bounds} is not fully "
                                f"covered in {preview_schema}.{target_table} and "
                                f"is missing from {dem_schema}.{source_table}. "
                                "Update area extends beyond the DEM coverage"
                            )
                            raise ValueError(msg)
                        preview_tile_exists = tiles.tile_exists(
                            job_session, preview_schema, target_table, envelope
                        )
                        pipeline = reader.PostgisReader(
                            dem_schema, source_table, primary_session, envelope.wkt
                        ) | writer.RasterPostgisWriter(
                            preview_schema,
                            target_table,
                            job_session,
                            mode=writer.WriterMode.UPDATE
                            if preview_tile_exists
                            else writer.WriterMode.INSERT,
                        )
                        pipeline.execute()

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def restore_stale_dem_preview(  # noqa: PLR0913
            primary_connection_uri: str,
            job_connection_uri: str,
            from_schema: str,
            from_table: str,
            to_schema: str,
            to_table: str,
        ) -> None:
            import shapely
            import sqlalchemy
            import sqlmodel
            from geoalchemy2.shape import to_shape
            from pinta_db.job_db.models.user import UpdateArea
            from pinta_processing import pipelines, writer

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                update_areas = job_session.exec(sqlmodel.select(UpdateArea)).all()
                buffer = pipelines.REGISTER_UPDATE_AREA_BUFFER
                # Pixels an earlier dissolve wrote that no update area covers any
                # more must be reset from the primary DEM.
                stale_area = shapely.union_all(
                    [
                        to_shape(area.dissolved_geom).buffer(buffer)
                        for area in update_areas
                        if area.dirty and area.dissolved_geom is not None
                    ]
                ) - shapely.union_all(
                    [to_shape(area.geom).buffer(buffer) for area in update_areas]
                )
                if stale_area.is_empty:
                    return

                pipeline = pipelines.postgis_to_postgis(
                    from_session=primary_session,
                    from_schema=from_schema,
                    from_table=from_table,
                    to_session=job_session,
                    to_schema=to_schema,
                    to_table=to_table,
                    tile_wkt=stale_area.wkt,
                    mode=writer.WriterMode.UPDATE,
                )
                pipeline.execute()

        @task.docker(
            # Parallel tasks merging into the same base/overview tiles can
            # deadlock on the concurrent row updates; retry to ride out the loser.
            **{
                **config.PINTA_CONTAINER_TASK_ARGS,
                "retries": 3,
                "retry_delay": datetime.timedelta(seconds=10),
            },
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def dissolve_update_area(
            primary_connection_uri: str,
            job_connection_uri: str,
            update_area_id: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db.job_db.models.user import UpdateArea
            from pinta_processing import pipelines

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                update_area = job_session.exec(
                    sqlmodel.select(UpdateArea).where(UpdateArea.id == update_area_id)
                ).first()
                if update_area is None:
                    # The area was deleted after it was listed; nothing to dissolve.
                    return

                pipeline = pipelines.dissolve_update_area(
                    primary_session=primary_session,
                    job_session=job_session,
                    update_area=update_area,
                )
                pipeline.execute()

                update_area.dirty = False
                update_area.dissolved_geom = update_area.geom
                job_session.add(update_area)
                job_session.commit()

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
            retries=3,
            retry_delay=datetime.timedelta(seconds=10),
        )
        def restore_update_area(
            primary_connection_uri: str,
            job_connection_uri: str,
            restore_id: str,
            geom_wkt: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_processing import pipelines, writer
            from shapely import wkt as shapely_wkt

            # The mapping key is needed by expand_kwargs even when only the
            # geometry drives the restore.
            del restore_id

            read_area = shapely_wkt.loads(geom_wkt).buffer(
                pipelines.REGISTER_UPDATE_AREA_BUFFER
            )

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                pipeline = pipelines.postgis_to_postgis(
                    from_session=primary_session,
                    from_schema=FROM_DB_SCHEMA,
                    from_table=FROM_DB_TABLE,
                    to_session=job_session,
                    to_schema=TO_DB_SCHEMA,
                    to_table=TO_DB_TABLE,
                    tile_wkt=read_area.wkt,
                    mode=writer.WriterMode.UPDATE,
                )
                pipeline.execute()

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_connection_uri = config.connection_uri_template("pinta_job_db")
        job_admin_connection_uri = config.connection_uri_template("pinta_job_db_admin")

        prod_area_id = "{{ params.id }}"

        status_started = set_processing_status_started(
            primary_connection_uri, prod_area_id
        )
        database_name = cast(
            "str", get_database_name(primary_connection_uri, prod_area_id)
        )
        job_db_uri = cast(
            "str",
            build_job_connection_uri_task(
                base_uri=job_connection_uri,
                database_name=database_name,
            ),
        )

        # The editor write privileges were granted by the job database owner,
        # and Postgres only lets the grantor take them back, so the lock runs on
        # the admin connection instead of the processing worker one.
        job_admin_db_uri = cast(
            "str",
            build_job_connection_uri_task.override(
                task_id="build_job_admin_connection_uri"
            )(
                base_uri=job_admin_connection_uri,
                database_name=database_name,
            ),
        )
        revoke_qgis_write_access = revoke_update_area_write_access(job_admin_db_uri)
        restore_qgis_write_access = restore_update_area_write_access(
            job_admin_db_uri, enabled=should_restore_write_access()
        )

        dirty_update_areas = find_dirty_update_areas(job_db_uri)
        restore_areas_list = find_restore_areas(job_db_uri)

        ensured_areas = ensure_dem_preview_coverage.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
        ).expand_kwargs(dirty_update_areas)

        restore_dem = restore_stale_dem_preview(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            from_schema=FROM_DB_SCHEMA,
            from_table=FROM_DB_TABLE,
            to_schema=TO_DB_SCHEMA,
            to_table=TO_DB_TABLE,
        )

        dissolved_areas = dissolve_update_area.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
        ).expand_kwargs(dirty_update_areas)

        restored_areas = restore_update_area.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
        ).expand_kwargs(restore_areas_list)

        deleted_restore_rows = delete_restore_area.partial(
            connection_uri=job_db_uri,
        ).expand_kwargs(restore_areas_list)

        status_completed = set_processing_status_completed(
            primary_connection_uri, prod_area_id
        )
        status_failed = set_processing_status_failed(
            primary_connection_uri, prod_area_id
        )

        # Stamp STARTED before any work, then run the dissolve chain. The
        # areas may extend outside the initialized dem_preview coverage, so
        # the missing tiles are copied in before any area is dissolved.
        status_started >> database_name

        job_admin_db_uri >> revoke_qgis_write_access >> dirty_update_areas
        revoke_qgis_write_access >> restore_areas_list

        dirty_update_areas >> ensured_areas >> restore_dem >> dissolved_areas
        restore_areas_list >> restored_areas >> deleted_restore_rows

        dissolved_areas >> restore_qgis_write_access
        deleted_restore_rows >> restore_qgis_write_access

        # Resolve the final status off every task that can fail (each is a direct
        # upstream, so ONE_FAILED still fires when an early step fails and the
        # mapped task never runs). NONE_FAILED marks COMPLETED otherwise.
        processing_steps = [
            status_started,
            database_name,
            job_db_uri,
            job_admin_db_uri,
            revoke_qgis_write_access,
            dirty_update_areas,
            restore_areas_list,
            ensured_areas,
            restore_dem,
            dissolved_areas,
            restored_areas,
            deleted_restore_rows,
            restore_qgis_write_access,
        ]
        processing_steps >> status_completed
        processing_steps >> status_failed

    return dissolve_update_areas_dag()


DAG_ID = constants.DAG_ID_DISSOLVE_UPDATE_AREAS

globals()[DAG_ID] = create_dissolve_update_areas_dag(dag_id=DAG_ID)
