# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

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
    find_production_area_tile_geometries,
    get_database_name,
    initialize_dem_tables,
    merge_dem_staging_tables,
)

FROM_DB_SCHEMA = PrimarySchema.DEM.value
FROM_DB_TABLE = PrimaryDem.__tablename__
TO_DB_SCHEMA = Schema.USER.value
TO_DB_TABLE = DemPreview.__tablename__


def _get_max_parallel_pipelines() -> int:
    # Reuses the reference DEM parallelism variable
    var = AirflowVariable.CALCULATE_REFERENCE_DEM_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def _get_staging_tables() -> int:
    # Reuses the reference DEM staging tables variable
    var = AirflowVariable.CALCULATE_REFERENCE_DEM_STAGING_TABLES
    staging_tables = int(Variable.get(var, 1))
    if staging_tables < 0:
        msg = f"{var} must be at least 0"
        raise ValueError(msg)
    return staging_tables


def create_initialize_dem_preview_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Initialize DEM preview",
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
    def initialize_dem_preview_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def copy_dem_preview(  # noqa: PLR0913
            primary_connection_uri: str,
            job_connection_uri: str,
            tile_wkt: str,
            staging_tables: int,
            from_schema: str,
            from_table: str,
            to_schema: str,
            to_table: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_processing import pipelines

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
                    from_schema=from_schema,
                    from_table=from_table,
                    to_session=job_session,
                    to_schema=to_schema,
                    to_table=to_table,
                    tile_wkt=tile_wkt,
                    staging_tables=staging_tables,
                )
                pipeline.execute()

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_connection_uri = config.connection_uri_template("pinta_job_db")
        staging_tables = _get_staging_tables()

        prod_area_id = "{{ params.id }}"
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
        tile_wkt_list = find_production_area_tile_geometries.override(
            task_id="find_production_area"
        )(primary_connection_uri, prod_area_id)

        initialize_task = initialize_dem_tables(
            job_db_uri, TO_DB_SCHEMA, TO_DB_TABLE, staging_tables
        )
        copied_tiles = copy_dem_preview.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            staging_tables=staging_tables,
            from_schema=FROM_DB_SCHEMA,
            from_table=FROM_DB_TABLE,
            to_schema=TO_DB_SCHEMA,
            to_table=TO_DB_TABLE,
        ).expand(tile_wkt=tile_wkt_list)
        (
            tile_wkt_list
            >> initialize_task
            >> copied_tiles
            >> merge_dem_staging_tables(
                job_db_uri, TO_DB_SCHEMA, TO_DB_TABLE, staging_tables
            )
        )

    return initialize_dem_preview_dag()


DAG_ID = constants.DAG_ID_INITIALIZE_DEM_PREVIEW

globals()[DAG_ID] = create_initialize_dem_preview_dag(dag_id=DAG_ID)
