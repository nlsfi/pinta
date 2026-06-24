# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import cast

from airflow.sdk import DAG, Param, TriggerRule, Variable, dag, task
from pinta_common import constants

from pinta_dags import config
from pinta_dags.config import AirflowVariable

DB_SCHEMA = "reference"
DB_TABLE = "dem"
JOB_TEMPLATE_NAME = "job_template"
CRS = "EPSG:3067"
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


def build_job_connection_uri(
    base_uri: str,
    database_name: str,
) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(base_uri)
    new_path = f"/{database_name}"
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            new_path,
            parts.query,
            parts.fragment,
        )
    )


def create_calculate_reference_dem_dag(  # noqa: C901, PLR0915
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
    def calculate_reference_dem_dag() -> None:  # noqa: C901, PLR0915

        @task
        def build_job_connection_uri_task(
            base_uri: str,
            database_name: str,
        ) -> str:
            return build_job_connection_uri(
                base_uri,
                database_name,
            )

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def find_production_area(
            connection_uri: str,
            production_area_id: str,
            job_database_name: str,
        ) -> list[str]:
            import sqlalchemy
            import sqlmodel
            from pinta_db.primary_db.models.management import (
                ProcessingStatus,
                ProductionArea,
            )

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                statement = sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
                file_paths = []
                area_in_db = session.exec(statement).first()
                if area_in_db:
                    area_in_db.database_name = job_database_name
                    area_in_db.processing_status = ProcessingStatus.STARTED
                    tiles = area_in_db.tiles
                    file_paths = [tile.file_path for tile in tiles]
                    session.commit()
                return file_paths

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS, trigger_rule=TriggerRule.ALL_SUCCESS
        )
        def set_processing_status_completed(
            connection_uri: str, production_area_id: str
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db.primary_db.models.management import (
                ProcessingStatus,
                ProductionArea,
            )

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                statement = sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
                area_in_db = session.exec(statement).first()
                if area_in_db:
                    area_in_db.processing_status = ProcessingStatus.COMPLETED
                    session.commit()

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS, trigger_rule=TriggerRule.ONE_FAILED
        )
        def set_processing_status_failed(
            connection_uri: str, production_area_id: str
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db.primary_db.models.management import (
                ProcessingStatus,
                ProductionArea,
            )

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                statement = sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
                area_in_db = session.exec(statement).first()
                if area_in_db:
                    area_in_db.processing_status = ProcessingStatus.FAILURE
                    session.commit()

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def create_job_database(
            connection_uri: str, database_name: str, template_name: str
        ) -> None:
            import sqlalchemy
            import sqlmodel

            engine = sqlalchemy.create_engine(
                connection_uri, isolation_level="AUTOCOMMIT"
            )
            with sqlmodel.Session(engine) as session:
                exists_statement = sqlalchemy.text(
                    "SELECT 1 FROM pg_database WHERE datname = :database_name"
                ).bindparams(database_name=database_name)

                result = session.exec(
                    exists_statement  # type: ignore[call-overload]
                ).first()

                if result:
                    # Database already exists
                    return

                statement = sqlalchemy.text(
                    f'CREATE DATABASE "{database_name}" WITH TEMPLATE "{template_name}"'
                )
                session.exec(statement)  # type: ignore[call-overload]
                session.commit()

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def initialize_dem_tables(
            connection_uri: str,
            schema: str,
            table: str,
            staging_tables: int,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db_utils.postgis import raster

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                raster.initialize_raster_table(
                    session,
                    schema,
                    table,
                    staging_tables,
                )
                raster.initialize_overview_tables(
                    session,
                    schema,
                    table,
                    staging_tables,
                )

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
            crs: str,
            staging_tables: int,
            extra_lastools_params: dict | None = None,
        ) -> None:
            from pathlib import Path

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

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def merge_dem_staging_tables(
            connection_uri: str, schema: str, table: str, staging_tables: int
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db_utils.postgis import raster

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                raster.merge_staging_tables(
                    schema,
                    table,
                    staging_tables=staging_tables,
                    session=session,
                )
                for level in raster.DEFAULT_OVERVIEW_LEVELS:
                    overview_table = raster.OVERVIEW_TABLE_NAME.format(
                        level=level, table_name=table
                    )
                    raster.merge_staging_tables(
                        schema,
                        overview_table,
                        staging_tables=staging_tables,
                        session=session,
                    )

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_admin_connection_uri = config.connection_uri_template("pinta_job_db_admin")
        job_connection_uri = config.connection_uri_template("pinta_job_db")

        prod_area_id = "{{ params.id }}"
        job_database_name = f"job_{prod_area_id}"
        file_paths = find_production_area(
            primary_connection_uri, prod_area_id, job_database_name
        )
        create_job_database_task = create_job_database(
            job_admin_connection_uri, job_database_name, JOB_TEMPLATE_NAME
        )

        job_db_uri = cast(
            "str",
            build_job_connection_uri_task(
                base_uri=job_connection_uri,
                database_name=job_database_name,
            ),
        )

        pixel_size = "{{ var.value.pinta_db_dem_pixel_size }}"
        blast2dem_task = blast2dem.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            step=pixel_size,
            keep_class=BLAST2DEM_KEEP_CLASS,
            crs=CRS,
            staging_tables=_get_staging_tables(),
        )

        initialize_task = initialize_dem_tables(
            job_db_uri, DB_SCHEMA, DB_TABLE, _get_staging_tables()
        )
        processed_files = blast2dem_task.expand(input_path=file_paths)
        pipeline = (
            create_job_database_task
            >> file_paths
            >> initialize_task
            >> processed_files
            >> merge_dem_staging_tables(
                job_db_uri, DB_SCHEMA, DB_TABLE, _get_staging_tables()
            )
        )

        pipeline >> set_processing_status_completed(
            primary_connection_uri, prod_area_id
        )
        pipeline >> set_processing_status_failed(primary_connection_uri, prod_area_id)

    return calculate_reference_dem_dag()


DAG_ID = constants.DAG_ID_CALCULATE_REFERENCE_DEM

globals()[DAG_ID] = create_calculate_reference_dem_dag(dag_id=DAG_ID)
