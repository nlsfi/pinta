# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import datetime
from typing import cast

from airflow.sdk import DAG, Param, Variable, dag, task
from pinta_common import constants

from pinta_dags import config
from pinta_dags.config import AirflowVariable
from pinta_dags.tasks import (
    build_job_connection_uri_task,
    find_dirty_update_areas,
    get_database_name,
    set_processing_status_completed,
    set_processing_status_failed,
    set_processing_status_started,
)


def _get_max_parallel_pipelines() -> int:
    var = AirflowVariable.DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES
    max_parallel = int(Variable.get(var, 4))
    if max_parallel < 1:
        msg = f"{var} must be at least 1"
        raise ValueError(msg)
    return max_parallel


def create_dissolve_update_areas_dag(
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
            )
        },
        is_paused_upon_creation=False,
    )
    def dissolve_update_areas_dag() -> None:
        # Precondition: the production area must already have its job database
        # provisioned and database_name set for production area by orchestrator DAG.

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            max_active_tis_per_dag=_get_max_parallel_pipelines(),
            # Parallel tasks merging into the same base/overview tiles can
            # deadlock on the concurrent row updates; retry to ride out the loser.
            retries=3,
            retry_delay=datetime.timedelta(seconds=10),
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
                job_session.add(update_area)
                job_session.commit()

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

        dissolved_areas = dissolve_update_area.partial(
            primary_connection_uri=primary_connection_uri,
            job_connection_uri=job_db_uri,
        ).expand_kwargs(dirty_update_areas)

        status_completed = set_processing_status_completed(
            primary_connection_uri, prod_area_id
        )
        status_failed = set_processing_status_failed(
            primary_connection_uri, prod_area_id
        )

        # Stamp STARTED before any work, then run the dissolve chain.
        status_started >> database_name
        dirty_update_areas >> dissolved_areas

        # Resolve the final status off every task that can fail (each is a direct
        # upstream, so ONE_FAILED still fires when an early step fails and the
        # mapped task never runs). NONE_FAILED marks COMPLETED otherwise.
        processing_steps = [
            status_started,
            database_name,
            job_db_uri,
            dirty_update_areas,
            dissolved_areas,
        ]
        processing_steps >> status_completed
        processing_steps >> status_failed

    return dissolve_update_areas_dag()


DAG_ID = constants.DAG_ID_DISSOLVE_UPDATE_AREAS

globals()[DAG_ID] = create_dissolve_update_areas_dag(dag_id=DAG_ID)
