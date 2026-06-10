# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""DAG that processes production area metadata when point cloud files change."""

import datetime

from airflow.sdk import DAG, chain, dag, task
from pinta_common import constants

from pinta_dags import config
from pinta_dags.sensors.folder_hash_sensor import FolderHashSensor


def create_process_production_areas_dag(
    *,
    dag_id: str,
) -> DAG:
    """Create and return the process production areas DAG."""

    @dag(
        dag_id=dag_id,
        tags=[dag_id],
        dag_display_name="Process production areas",
        schedule=datetime.timedelta(minutes=5),
        is_paused_upon_creation=False,
    )
    def process_production_areas_dag() -> None:
        check_for_changes = FolderHashSensor(
            task_id="check_for_changes",
            base_path="{{ var.value.pinta_point_cloud_base_path }}",
        )

        @task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
        def process_areas(
            connection_uri: str, base_path: str, changed_folders: list[dict[str, str]]
        ) -> None:
            from pathlib import Path

            import sqlalchemy
            import sqlmodel
            from pinta_processing.scripts import process_metadata

            engine = sqlalchemy.create_engine(connection_uri)
            with sqlmodel.Session(engine) as session:
                for change in changed_folders:
                    process_metadata.process_metadata_in_folder(
                        Path(base_path) / change["folder_path"], session
                    )

        @task
        def store_checksums(changed_folders: list[dict[str, str]]) -> None:
            from pathlib import Path

            from airflow.sdk import Variable

            for change in changed_folders:
                Variable.set(Path(change["folder_path"]).name, change["new_hash"])

        changed = check_for_changes.output
        areas_result = process_areas(
            config.connection_uri_template("pinta_processing_db"),
            "{{ var.value.pinta_container_target_base_path }}",
            changed,
        )
        checksums_task = store_checksums(changed)
        chain(areas_result, checksums_task)

    return process_production_areas_dag()


DAG_ID = constants.DAG_ID_PROCESS_PRODUCTION_AREAS

globals()[DAG_ID] = create_process_production_areas_dag(dag_id=DAG_ID)
