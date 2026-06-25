# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import cast

from airflow.providers.standard.operators.trigger_dagrun import (  # noqa: SC200
    TriggerDagRunOperator,
)
from airflow.sdk import DAG, Param, TriggerRule, dag, task
from pinta_common import constants, env

from pinta_dags import config


def create_calculate_rasters_for_production_area_dag(  # noqa: C901, PLR0915
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Calculate rasters for production area",
        schedule=None,
        # Render templates to native Python objects so boolean params stay bools.
        render_template_as_native_obj=True,
        params={
            "id": Param(
                "",
                type="string",
                format="uuid",
                description="Production area id as UUID",
            ),
            "calculate_reference_dem": Param(
                default=True,
                type="boolean",
                description="Trigger calculate reference DEM DAG",
            ),
            "calculate_dem_diff": Param(
                default=True,
                type="boolean",
                description="Trigger calculate DEM diff DAG",
            ),
        },
        is_paused_upon_creation=False,
    )
    def calculate_rasters_for_production_area_dag() -> None:  # noqa: PLR0915

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def ensure_job_database(
            primary_connection_uri: str,
            job_admin_connection_uri: str,
            production_area_id: str,
            template_name: str,
        ) -> None:
            import sqlalchemy
            import sqlmodel
            from pinta_db.primary_db.models.management import (
                ProcessingStatus,
                ProductionArea,
            )

            engine = sqlalchemy.create_engine(primary_connection_uri)
            with sqlmodel.Session(engine) as session:
                area = session.exec(
                    sqlmodel.select(ProductionArea).where(
                        ProductionArea.id == production_area_id
                    )
                ).first()
                if area is None:
                    msg = f"Production area {production_area_id} not found"
                    raise ValueError(msg)

                if area.database_name is None:
                    area.database_name = f"job_{production_area_id}"
                database_name = area.database_name
                area.processing_status = ProcessingStatus.STARTED
                session.commit()

            admin_engine = sqlalchemy.create_engine(
                job_admin_connection_uri, isolation_level="AUTOCOMMIT"
            )
            with sqlmodel.Session(admin_engine) as admin_session:
                exists = admin_session.exec(
                    sqlalchemy.text(
                        "SELECT 1 FROM pg_database WHERE datname = :database_name"
                    ).bindparams(database_name=database_name)  # type: ignore[call-overload]
                ).first()
                if exists:
                    return
                admin_session.exec(
                    sqlalchemy.text(
                        f'CREATE DATABASE "{database_name}" '
                        f'WITH TEMPLATE "{template_name}"'
                    )  # type: ignore[call-overload]
                )
                admin_session.commit()

        @task.short_circuit(ignore_downstream_trigger_rules=False)
        def should_run(*, requested: bool) -> bool:
            # Skip only the directly downstream trigger when not requested.
            return requested

        trigger_calculate_reference_dem = TriggerDagRunOperator(
            task_id="trigger_calculate_reference_dem",
            trigger_dag_id=constants.DAG_ID_CALCULATE_REFERENCE_DEM,
            conf={"id": "{{ params.id }}"},
            wait_for_completion=True,
        )

        trigger_calculate_dem_diff = TriggerDagRunOperator(
            task_id="trigger_calculate_dem_diff",
            trigger_dag_id=constants.DAG_ID_CALCULATE_DEM_DIFF,
            conf={"id": "{{ params.id }}"},
            wait_for_completion=True,
        )

        @task.docker(
            **config.PINTA_CONTAINER_TASK_ARGS,
            trigger_rule=TriggerRule.NONE_FAILED,
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
            **config.PINTA_CONTAINER_TASK_ARGS,
            trigger_rule=TriggerRule.ONE_FAILED,
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

        primary_connection_uri = config.connection_uri_template("pinta_processing_db")
        job_admin_connection_uri = config.connection_uri_template("pinta_job_db_admin")
        prod_area_id = "{{ params.id }}"

        ensure_database = ensure_job_database(
            primary_connection_uri,
            job_admin_connection_uri,
            prod_area_id,
            env.JOB_TEMPLATE_NAME,
        )

        reference_gate = should_run.override(
            task_id="should_calculate_reference_dem",
        )(requested=cast("bool", "{{ params.calculate_reference_dem }}"))
        # Runs once the reference DEM trigger has resolved (also when it was
        # skipped) so the DEM diff can still run on its own.
        diff_gate = should_run.override(
            task_id="should_calculate_dem_diff",
            trigger_rule=TriggerRule.NONE_FAILED,
        )(requested=cast("bool", "{{ params.calculate_dem_diff }}"))

        triggers = [trigger_calculate_reference_dem, trigger_calculate_dem_diff]
        status_completed = set_processing_status_completed(
            primary_connection_uri, prod_area_id
        )
        status_failed = set_processing_status_failed(
            primary_connection_uri, prod_area_id
        )

        # Gate each trigger on its flag; the DEM diff runs after the reference
        # DEM so it can compare against freshly computed reference rasters.
        ensure_database >> reference_gate >> trigger_calculate_reference_dem
        trigger_calculate_reference_dem >> diff_gate >> trigger_calculate_dem_diff
        # Also depend on ensure_database so a failure there (before any trigger
        # runs) still resolves the processing status instead of leaving the
        # production area stuck in STARTED.
        [ensure_database, *triggers] >> status_completed
        [ensure_database, *triggers] >> status_failed

    return calculate_rasters_for_production_area_dag()


DAG_ID = constants.DAG_ID_CALCULATE_RASTERS_FOR_PRODUCTION_AREA

globals()[DAG_ID] = create_calculate_rasters_for_production_area_dag(dag_id=DAG_ID)
