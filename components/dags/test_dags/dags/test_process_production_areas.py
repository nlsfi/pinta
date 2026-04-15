# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from airflow import sdk
from airflow.models import DagBag, dagbag
from airflow.sdk import Variable

from pinta_dags.dags import process_production_areas

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = process_production_areas.create_process_production_areas_dag(
        dag_id=f"some_id_{uuid.uuid4()}"
    )

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    dagbag.sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv(
        "AIRFLOW_CONN_PINTA_PROCESSING_DB_CONTAINER", "postgres://mockaddr:123/db"
    )


@pytest.fixture
def mock_task(
    mocker: "MockerFixture",
) -> "MagicMock":
    return mocker.patch(
        "pinta_dags.dags.process_production_areas.sdk.task",
        wraps=sdk.task,
    )


def test_process_production_areas_dag_all_tasks(
    mock_task: "MagicMock",
) -> None:
    create_dag_to_test()

    mock_task.assert_called_once()
    mock_task.docker.assert_called_once()


def test_process_production_areas_dag_runs_workflow(
    tmp_path: Path,
    monkeypatch: "pytest.MonkeyPatch",
    mocker: "MockerFixture",
) -> None:
    area_dir = tmp_path / "2025" / "production_area_1"
    area_dir.mkdir(parents=True)
    (area_dir / "tile.laz").write_bytes(b"fake laz data")

    monkeypatch.setenv("AIRFLOW_VAR_PINTA_POINT_CLOUD_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CONTAINER_BASE_PATH", str(tmp_path))

    mock_process_metadata_module = mocker.MagicMock()
    mock_variable_set = mocker.patch.object(Variable, "set")

    # Create the DAG before patching to avoid interfering with Airflow DB (also uses sqlalchemy)
    dag = create_dag_to_test()

    # Patch only the processing module — do NOT mock sqlalchemy globally as Airflow uses it
    mocker.patch.dict(
        "sys.modules",
        {"pinta_processing.scripts.process_metadata": mock_process_metadata_module},
    )

    dag.test()

    mock_process_metadata_module.process_metadata_in_folder.assert_called_once()
    call_path = mock_process_metadata_module.process_metadata_in_folder.call_args.args[
        0
    ]
    assert call_path == area_dir

    mock_variable_set.assert_called_with("production_area_1", mocker.ANY)
