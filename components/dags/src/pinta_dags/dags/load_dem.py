# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

from airflow.sdk import DAG, Param, Variable, dag, task
from pinta_common import constants
from pinta_db.primary_db.models.dem import Dem
from pinta_db.primary_db.schema import Schema

from pinta_dags import config
from pinta_dags.config import AirflowVariable

DEM_SCHEMA = Schema.DEM.value
DEM_TABLE_NAME = Dem.__tablename__


def _get_max_parallel_pipelines() -> int:
    var = AirflowVariable.LOAD_DEM_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def _get_staging_tables() -> int:
    var = AirflowVariable.LOAD_DEM_STAGING_TABLES
    staging_tables = int(Variable.get(var, 1))
    if staging_tables < 0:
        msg = f"{var} must be at least 0"
        raise ValueError(msg)
    return staging_tables


def _container_task_args_with_environment(
    environment: dict[str, str],
) -> dict[str, Any]:
    return {
        **config.PINTA_CONTAINER_TASK_ARGS,
        "environment": {
            **config.PINTA_CONTAINER_TASK_ARGS["environment"],
            **environment,
        },
    }


def load_dem_dag(
    *,
    dag_id: str,
) -> DAG:

    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Load dem from files",
        schedule=None,
        max_active_runs=1,
        params={
            "folder": Param(
                "",
                type="string",
                description=(
                    "Absolute path inside the processing container. "
                    "Data is mounted under /dem"
                ),
            )
        },
        is_paused_upon_creation=False,
    )
    def load_dem_from_files_dag() -> None:

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def initialize_dem_tables(
            connection_uri: str,
            staging_tables: int,
            schema: str,
            table_name: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db_utils.postgis import raster

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                raster.initialize_raster_table(
                    session, schema, table_name, staging_tables=staging_tables
                )
                raster.initialize_overview_tables(
                    session, schema, table_name, staging_tables=staging_tables
                )

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def list_dem_files(data_dir: str) -> list[str]:
            from pathlib import Path

            folder = Path(data_dir)
            return [str(file_path) for file_path in sorted(folder.glob("*.zip"))]

        @task
        def require_dem_files(files: list[str]) -> list[str]:
            from airflow.sdk.exceptions import AirflowSkipException

            if not files:
                msg = "No DEM files found to process."
                raise AirflowSkipException(msg)
            return files

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def process_dem_file(
            connection_uri: str,
            input_path: str,
            staging_tables: int,
            schema: str,
            table_name: str,
        ) -> None:
            from pathlib import Path

            import sqlalchemy
            import sqlmodel
            from pinta_processing import pipelines

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                pipeline = pipelines.rasterio_to_postgis(
                    session=session,
                    input_path=Path(input_path),
                    schema=schema,
                    table_name=table_name,
                    staging_tables=staging_tables,
                )
                pipeline.execute()

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def merge_dem_staging_tables(
            connection_uri: str,
            staging_tables: int,
            schema: str,
            table_name: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db_utils.postgis import raster

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                raster.merge_staging_tables(
                    schema,
                    table_name,
                    staging_tables=staging_tables,
                    session=session,
                )
                for level in raster.DEFAULT_OVERVIEW_LEVELS:
                    overview_table = raster.OVERVIEW_TABLE_NAME.format(
                        level=level, table_name=table_name
                    )
                    raster.merge_staging_tables(
                        schema,
                        overview_table,
                        staging_tables=staging_tables,
                        session=session,
                    )

        connection_uri = config.connection_uri_template("pinta_processing_db")
        staging_tables = _get_staging_tables()
        files = list_dem_files("{{ params.folder }}")
        files_to_process = require_dem_files(files)
        process_dem_file_task = process_dem_file.partial(
            connection_uri=connection_uri,
            staging_tables=staging_tables,
            schema=DEM_SCHEMA,
            table_name=DEM_TABLE_NAME,
        )
        initialize_task = initialize_dem_tables(
            connection_uri,
            staging_tables,
            schema=DEM_SCHEMA,
            table_name=DEM_TABLE_NAME,
        )
        processed_files = process_dem_file_task.expand(input_path=files_to_process)
        (
            files_to_process
            >> initialize_task
            >> processed_files
            >> merge_dem_staging_tables(
                connection_uri,
                staging_tables,
                schema=DEM_SCHEMA,
                table_name=DEM_TABLE_NAME,
            )
        )

    return load_dem_from_files_dag()


DAG_ID = constants.DAG_ID_LOAD_DEM

globals()[DAG_ID] = load_dem_dag(dag_id=DAG_ID)
