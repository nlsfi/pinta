# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Example DAG with external venv task & connection URI variable."""

from airflow.sdk import DAG, dag, task


def create_print_hello_world_dag(
    *,
    dag_id: str,
) -> DAG:
    @dag(dag_id=dag_id, dag_display_name="Print hello world", schedule=None)
    def hello_world_dag() -> None:
        @task
        def hello_world_task(connection_uri: str) -> None:
            from pinta_processing.scripts import hello_world

            hello_world.log_hello_world(connection_uri)

        hello_world_task("{{ conn.pinta_processing_db.get_hook().sqlalchemy_url }}")

    return hello_world_dag()


DAG_ID = "print_hello_world"

globals()[DAG_ID] = create_print_hello_world_dag(dag_id=DAG_ID)
