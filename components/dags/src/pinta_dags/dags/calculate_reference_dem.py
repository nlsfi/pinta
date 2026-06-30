# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import cast

from airflow.sdk import DAG, Param, Variable, dag, task
from pinta_common import constants
from pinta_db.job_db.models.reference import Dem
from pinta_db.job_db.schema import Schema

from pinta_dags import config
from pinta_dags.config import AirflowVariable
from pinta_dags.tasks import (
    build_job_connection_uri_task,
    get_database_name,
    initialize_dem_tables,
    merge_dem_staging_tables,
)

DB_SCHEMA = Schema.REFERENCE.value
DB_TABLE = Dem.__tablename__
BLAST2DEM_KEEP_CLASS = [2]


def _get_max_parallel_pipelines() -> int:
    var = AirflowVariable.CALCULATE_REFERENCE_DEM_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def _get_staging_tables() -> int:
    var = AirflowVariable.CALCULATE_REFERENCE_DEM_STAGING_TABLES
    staging_tables = int(Variable.get(var, 1))
    if staging_tables < 0:
        msg = f"{var} must be at least 0"
        raise ValueError(msg)
    return staging_tables


def create_calculate_reference_dem_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Calculate reference dem",
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
    def calculate_reference_dem_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def find_production_area(
            connection_uri: str,
            production_area_id: str,
        ) -> list[str]:
            import sqlalchemy
            import sqlmodel
            from pinta_db.primary_db.models.management import ProductionArea

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                statement = sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
                area_in_db = session.exec(statement).first()
                if not area_in_db:
                    return []
                return [tile.file_path for tile in area_in_db.tiles]

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def blast2dem(  # noqa: PLR0913
            primary_connection_uri: str,
            job_connection_uri: str,
            input_path: str,
            step: int,
            keep_class: list[int],
            staging_tables: int,
            extra_lastools_params: dict | None = None,
        ) -> None:
            from pathlib import Path

            import sqlalchemy
            import sqlmodel
            from pinta_common import Settings
            from pinta_processing import pipelines

            crs = f"EPSG:{Settings.DB_SRID}"

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                pipeline = pipelines.blast2dem_to_postgis(
                    primary_session=primary_session,
                    job_session=job_session,
                    input_path=Path(input_path),
                    step=step,
                    keep_class=keep_class,
                    staging_tables=staging_tables,
                    crs=crs,
                    extra_lastools_params=extra_lastools_params,
                )
                pipeline.execute()

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_connection_uri = config.connection_uri_template("pinta_job_db")

        prod_area_id = "{{ params.id }}"
        database_name = cast(
            "str", get_database_name(primary_connection_uri, prod_area_id)
        )
        file_paths = find_production_area(primary_connection_uri, prod_area_id)

        job_db_uri = cast(
            "str",
            build_job_connection_uri_task(
                base_uri=job_connection_uri,
                database_name=database_name,
            ),
        )

        pixel_size = "{{ var.value.pinta_db_dem_pixel_size }}"
        blast2dem_task = blast2dem.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            step=pixel_size,
            keep_class=BLAST2DEM_KEEP_CLASS,
            staging_tables=_get_staging_tables(),
        )

        initialize_task = initialize_dem_tables(
            job_db_uri, DB_SCHEMA, DB_TABLE, _get_staging_tables()
        )
        processed_files = blast2dem_task.expand(input_path=file_paths)
        (
            file_paths
            >> initialize_task
            >> processed_files
            >> merge_dem_staging_tables(
                job_db_uri, DB_SCHEMA, DB_TABLE, _get_staging_tables()
            )
        )

    return calculate_reference_dem_dag()


DAG_ID = constants.DAG_ID_CALCULATE_REFERENCE_DEM

globals()[DAG_ID] = create_calculate_reference_dem_dag(dag_id=DAG_ID)
