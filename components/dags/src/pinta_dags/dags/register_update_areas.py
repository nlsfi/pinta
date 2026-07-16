# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import datetime
from typing import cast

from airflow.providers.standard.operators.trigger_dagrun import (  # noqa: SC200
    TriggerDagRunOperator,
)
from airflow.sdk import DAG, Param, TriggerRule, Variable, dag, task
from pinta_common import constants
from pinta_db.job_db.models.user import DemPreview
from pinta_db.job_db.schema import Schema
from pinta_db.primary_db.models.dem import Dem as PrimaryDem
from pinta_db.primary_db.schema import Schema as PrimarySchema

from pinta_dags import config
from pinta_dags.config import AirflowVariable
from pinta_dags.tasks import (
    build_job_connection_uri_task,
    find_dirty_update_areas,
    find_update_area_geometries,
    get_database_name,
    set_processing_status_completed,
    set_processing_status_failed,
    set_processing_status_started,
)

FROM_DB_SCHEMA = Schema.USER.value
FROM_DB_TABLE = DemPreview.__tablename__
TO_DB_SCHEMA = PrimarySchema.DEM.value
TO_DB_TABLE = PrimaryDem.__tablename__


def _get_max_parallel_pipelines() -> int:
    var = AirflowVariable.REGISTER_UPDATE_AREAS_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def create_register_update_areas_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Register update areas",
        schedule=None,
        params={
            "id": Param(
                "",
                type="string",
                format="uuid",
                description=("Production area id as UUID"),
            )
        },
        is_paused_upon_creation=False,
    )
    def register_update_areas_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task.short_circuit(ignore_downstream_trigger_rules=False)
        def should_dissolve(dirty_update_areas: list[dict[str, str]]) -> bool:
            # Skip only the directly downstream dissolve trigger when every
            # update area is already clean.
            return len(dirty_update_areas) > 0

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
            # Parallel tasks merging into the same base/overview tiles can
            # deadlock on the concurrent row updates, retry.
            retries=3,
            retry_delay=datetime.timedelta(seconds=10),
        )
        def register_update_area(  # noqa: PLR0913
            primary_connection_uri: str,
            job_connection_uri: str,
            geom_wkt: str,
            from_schema: str,
            from_table: str,
            to_schema: str,
            to_table: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_processing import pipelines, writer
            from shapely import wkt as shapely_wkt

            # Read the preview buffered past the seam the dissolve interpolated
            # outside the update area, so every changed pixel is registered.
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
                    from_session=job_session,
                    from_schema=from_schema,
                    from_table=from_table,
                    to_session=primary_session,
                    to_schema=to_schema,
                    to_table=to_table,
                    tile_wkt=read_area.wkt,
                    staging_tables=0,
                    mode=writer.WriterMode.UPDATE,
                )
                pipeline.execute()

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_connection_uri = config.connection_uri_template("pinta_job_db")

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
        dirty_update_areas = find_dirty_update_areas(job_db_uri)
        dissolve_gate = should_dissolve(dirty_update_areas)

        trigger_dissolve_update_areas = TriggerDagRunOperator(
            task_id="trigger_dissolve_update_areas",
            trigger_dag_id=constants.DAG_ID_DISSOLVE_UPDATE_AREAS,
            conf={"id": "{{ params.id }}"},
            wait_for_completion=True,
            poke_interval=config.TRIGGER_POKE_INTERVAL_SECONDS,
        )

        # Runs once the dissolve trigger has resolved (also when it was
        # skipped because nothing was dirty).
        update_area_geometries = find_update_area_geometries.override(
            trigger_rule=TriggerRule.NONE_FAILED
        )(job_db_uri)

        registered_areas = register_update_area.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            from_schema=FROM_DB_SCHEMA,
            from_table=FROM_DB_TABLE,
            to_schema=TO_DB_SCHEMA,
            to_table=TO_DB_TABLE,
        ).expand(geom_wkt=update_area_geometries)

        status_completed = set_processing_status_completed(
            primary_connection_uri, prod_area_id
        )
        status_failed = set_processing_status_failed(
            primary_connection_uri, prod_area_id
        )

        # Stamp STARTED before any work, then dissolve dirty areas (if any)
        # before registering every update area.
        status_started >> database_name
        dissolve_gate >> trigger_dissolve_update_areas >> update_area_geometries
        update_area_geometries >> registered_areas

        # Resolve the final status off every task that can fail (each is a direct
        # upstream, so ONE_FAILED still fires when an early step fails and the
        # mapped task never runs). NONE_FAILED marks COMPLETED otherwise.
        processing_steps = [
            status_started,
            database_name,
            job_db_uri,
            dirty_update_areas,
            trigger_dissolve_update_areas,
            update_area_geometries,
            registered_areas,
        ]
        processing_steps >> status_completed
        processing_steps >> status_failed

    return register_update_areas_dag()


DAG_ID = constants.DAG_ID_REGISTER_UPDATE_AREAS

globals()[DAG_ID] = create_register_update_areas_dag(dag_id=DAG_ID)
