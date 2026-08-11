# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any, cast

from airflow.sdk import DAG, Param, Variable, dag, task
from pinta_common import MASK_OGR_ENV_PREFIX, constants

from pinta_dags import config
from pinta_dags.config import AirflowVariable
from pinta_dags.tasks import (
    build_job_connection_uri_task,
    find_production_area_geometry,
    get_database_name,
)


def _mask_container_task_args() -> dict[str, Any]:
    """Container task args carrying the configured mask sources into the task.

    The sources are configured as one Airflow Variable holding a JSON object of
    source name to GDAL/OGR data source, and are handed to the processing
    component as the prefixed environment variables it reads them from.
    """
    var = AirflowVariable.MASK_OGR_SOURCES
    sources = Variable.get(var, {}, deserialize_json=True)
    if not isinstance(sources, dict):
        msg = f"{var} must be a JSON object of source name to data source"
        raise TypeError(msg)

    return {
        **config.PINTA_CONTAINER_TASK_ARGS,
        "environment": {
            **config.PINTA_CONTAINER_TASK_ARGS["environment"],
            **{
                f"{MASK_OGR_ENV_PREFIX}{name}": str(data_source)
                for name, data_source in sorted(sources.items())
            },
        },
    }


def create_suggest_masked_update_areas_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Suggest masked update areas",
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
    def suggest_masked_update_areas_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.
        # The elevations are read from the primary DEM, so no reference DEM is
        # needed, only the suggestions are stored in the job database.

        # The masks are read, checked against the DEM and stored in one task:
        # a polygon can be hundreds of kilobytes of WKT, which is far past what
        # fits in the task arguments of a containerized task.
        @task.docker(**_mask_container_task_args())
        def insert_update_area_suggestions(
            primary_connection_uri: str,
            job_connection_uri: str,
            production_area_wkt: str,
        ) -> None:
            """Suggest update areas for the masks the DEM does not model flat."""
            import sqlalchemy
            import sqlmodel
            from pinta_processing import reader
            from pinta_processing.scripts import masked_update_area_suggestions

            with (
                sqlmodel.Session(
                    sqlalchemy.create_engine(primary_connection_uri)
                ) as primary_session,
                sqlmodel.Session(
                    sqlalchemy.create_engine(job_connection_uri)
                ) as job_session,
            ):
                masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
                    primary_session,
                    job_session,
                    reader.OgrReader.sources_from_environment(),
                    area_of_interest=production_area_wkt,
                )

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_connection_uri = config.connection_uri_template("pinta_job_db")

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

        # The masks cover the whole country, only the ones overlapping the
        # production area have a DEM to check against.
        production_area_wkt = cast(
            "str",
            find_production_area_geometry(primary_connection_uri, prod_area_id),
        )

        insert_update_area_suggestions(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
            production_area_wkt=production_area_wkt,
        )

    return suggest_masked_update_areas_dag()


DAG_ID = constants.DAG_ID_SUGGEST_MASKED_UPDATE_AREAS

globals()[DAG_ID] = create_suggest_masked_update_areas_dag(dag_id=DAG_ID)
