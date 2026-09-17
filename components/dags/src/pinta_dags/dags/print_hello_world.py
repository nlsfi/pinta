# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Example DAG with external venv task & connection URI variable."""

from airflow.sdk import DAG, Param, chain, dag, task
from pinta_common import constants, flags

from pinta_dags import config


def create_print_hello_world_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        dag_display_name="Print hello world",
        schedule=None,
        tags=[dag_id],
        params={
            "name": Param(
                "World",
                type="string",
                description=f"Name to greet in the log line. "
                f"If {flags.FLAG_TEST_DAG_PRINT_CURRENT_TIME.name} "
                f"is enabled, the current time will be printed as well.",
            ),
        },
        is_paused_upon_creation=False,
    )
    def hello_world_dag() -> None:
        @task
        def hello_world_task(connection_uri: str, name: str) -> None:
            import datetime

            from pinta_processing.scripts import hello_world

            text = connection_uri
            if flags.FLAG_TEST_DAG_PRINT_CURRENT_TIME:
                text += f" at {datetime.datetime.now(datetime.UTC)}"
            hello_world.log_hello_world(text, name=name)

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def hello_world_task_docker(connection_uri: str, name: str) -> None:
            import datetime

            from pinta_processing.scripts import hello_world

            text = connection_uri
            if flags.FLAG_TEST_DAG_PRINT_CURRENT_TIME:
                text += f" at {datetime.datetime.now(datetime.UTC)}"
            hello_world.log_hello_world(text, name=name)

        chain(
            hello_world_task(
                config.connection_uri_template("pinta_processing_db"),
                "{{ params.name }}",
            ),
            hello_world_task_docker(
                config.connection_uri_template("pinta_processing_db"),
                "{{ params.name }}",
            ),
        )

    return hello_world_dag()


DAG_ID = constants.DAG_ID_HELLO_WORLD

globals()[DAG_ID] = create_print_hello_world_dag(dag_id=DAG_ID)
