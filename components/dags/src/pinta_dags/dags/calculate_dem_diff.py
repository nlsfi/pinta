# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import cast

from airflow.sdk import DAG, Param, TriggerRule, Variable, dag, task
from pinta_common import constants
from pinta_db.job_db.models.reference import DiffGtThreshold, DiffLteThreshold
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
DB_TABLE_DIFF = DiffGtThreshold.__tablename__
DB_TABLE_DIFF_LTE_THRESHOLD = DiffLteThreshold.__tablename__


def _get_max_parallel_pipelines() -> int:
    max_parallel = int(
        Variable.get(AirflowVariable.CALCULATE_DEM_DIFF_MAX_PARALLEL_PIPELINES, 4)
    )
    if max_parallel < 1:
        var = AirflowVariable.CALCULATE_DEM_DIFF_MAX_PARALLEL_PIPELINES
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def _get_staging_tables() -> int:
    staging_tables = int(
        Variable.get(AirflowVariable.CALCULATE_DEM_DIFF_STAGING_TABLES, 1)
    )
    if staging_tables < 0:
        msg = f"{AirflowVariable.CALCULATE_DEM_DIFF_STAGING_TABLES} must be at least 0"
        raise ValueError(msg)
    return staging_tables


def create_calculate_dem_diff_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Calculate DEM diff",
        schedule=None,
        # Render templates to native Python objects so boolean params stay bools.
        render_template_as_native_obj=True,
        params={
            "id": Param(
                "",
                type="string",
                format="uuid",
                description=("Production area id as UUID"),
            ),
            "cluster": Param(
                default=True,
                type="boolean",
                description="Cluster difference polygons after diffs are calculated",
            ),
        },
        is_paused_upon_creation=False,
    )
    def calculate_dem_diff_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def find_production_area(
            connection_uri: str,
            production_area_id: str,
        ) -> list[str]:
            import sqlalchemy
            import sqlmodel
            from geoalchemy2.shape import to_shape
            from pinta_db.primary_db.models.management import ProductionArea

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                statement = sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
                area_in_db = session.exec(statement).first()
                if not area_in_db:
                    return []
                return [to_shape(tile.geom).wkt for tile in area_in_db.tiles]

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
        )
        def calculate_dem_diff(
            primary_connection_uri: str,
            job_connection_uri: str,
            tile_wkt: str,
            staging_tables: int,
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
                pipeline = pipelines.calculate_diff_models(
                    primary_session=primary_session,
                    job_session=job_session,
                    tile_wkt=tile_wkt,
                    staging_tables=staging_tables,
                )
                pipeline.execute()

        @task.short_circuit(ignore_downstream_trigger_rules=False)
        def should_cluster(*, requested: bool) -> bool:
            # Skip only the directly downstream clustering task when not requested.
            return requested

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def cluster_diff_polygons(job_connection_uri: str) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_processing.scripts import cluster

            engine = sqlalchemy.create_engine(job_connection_uri)
            with sqlmodel.Session(engine) as session:
                cluster.cluster_diff_polygons(session)

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
        tile_wkt_list = find_production_area(primary_connection_uri, prod_area_id)

        init_diff_task = initialize_dem_tables.override(
            task_id="initialize_diff_tables"
        )(job_db_uri, DB_SCHEMA, DB_TABLE_DIFF, staging_tables)
        init_diff_lte_threshold_task = initialize_dem_tables.override(
            task_id="initialize_diff_lte_threshold_tables"
        )(job_db_uri, DB_SCHEMA, DB_TABLE_DIFF_LTE_THRESHOLD, staging_tables)

        processed_tiles = calculate_dem_diff.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            staging_tables=staging_tables,
        ).expand(tile_wkt=tile_wkt_list)

        merge_diff_task = merge_dem_staging_tables.override(
            task_id="merge_diff_tables"
        )(job_db_uri, DB_SCHEMA, DB_TABLE_DIFF, staging_tables)
        merge_diff_lte_threshold_task = merge_dem_staging_tables.override(
            task_id="merge_diff_lte_threshold_tables"
        )(job_db_uri, DB_SCHEMA, DB_TABLE_DIFF_LTE_THRESHOLD, staging_tables)

        cluster_gate = should_cluster.override(
            task_id="should_cluster",
            trigger_rule=TriggerRule.NONE_FAILED,
        )(requested=cast("bool", "{{ params.cluster }}"))
        cluster_task = cluster_diff_polygons(job_db_uri)

        (
            tile_wkt_list
            >> [init_diff_task, init_diff_lte_threshold_task]
            >> processed_tiles
            >> [merge_diff_task, merge_diff_lte_threshold_task]
            >> cluster_gate
            >> cluster_task
        )

    return calculate_dem_diff_dag()


DAG_ID = constants.DAG_ID_CALCULATE_DEM_DIFF

globals()[DAG_ID] = create_calculate_dem_diff_dag(dag_id=DAG_ID)
