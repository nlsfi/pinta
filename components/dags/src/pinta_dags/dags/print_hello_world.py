# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Example DAG with external venv task & connection URI variable."""

from airflow.sdk import DAG, Param, chain, dag, task

from pinta_dags import config


def create_print_hello_world_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(
        dag_id=dag_id,
        dag_display_name="Print hello world",
        schedule=None,
        tags=["hello_world"],
        params={
            "name": Param(
                "World",
                type="string",
                description="Name to greet in the log line.",
            ),
        },
        is_paused_upon_creation=False,
    )
    def hello_world_dag() -> None:
        @task
        def hello_world_task(connection_uri: str, name: str) -> None:
            from pinta_processing.scripts import hello_world

            hello_world.log_hello_world(connection_uri, name=name)

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def hello_world_task_docker(connection_uri: str, name: str) -> None:
            from pinta_processing.scripts import hello_world

            hello_world.log_hello_world(connection_uri, name=name)

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


DAG_ID = "print_hello_world"

globals()[DAG_ID] = create_print_hello_world_dag(dag_id=DAG_ID)
