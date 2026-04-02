# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import re
import uuid
from typing import TYPE_CHECKING

import pytest
from airflow.models import DagBag
from airflow.models.dagbag import sync_bag_to_db
from airflow.sdk import task

from pinta_dags.dags.print_hello_world import create_print_hello_world_dag

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = create_print_hello_world_dag(dag_id=f"some_id_{uuid.uuid4()}")

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")


@pytest.fixture
def mock_log_hello_world(
    mocker: "MockerFixture",
) -> "MagicMock":
    mock_hello_world_module = mocker.MagicMock()
    mocker.patch.dict(
        "sys.modules", {"pinta_processing.scripts.hello_world": mock_hello_world_module}
    )
    return mock_hello_world_module.log_hello_world


@pytest.fixture
def mock_task(
    mocker: "MockerFixture",
) -> "MagicMock":
    return mocker.patch(
        "pinta_dags.dags.print_hello_world.task",
        wraps=task,
    )


def test_print_hello_world_dag_all_tasks(
    mock_task: "MagicMock",
):
    create_dag_to_test()

    mock_task.assert_called_once()
    mock_task.docker.assert_called_once()


def test_print_hello_world_dag_runs_workflow_log_call(
    mock_log_hello_world: "MagicMock",
    mocker: "MockerFixture",
):
    pattern = re.compile(r"^postgresql(?:\+psycopg)?://mockaddr:123/db$")

    dag = create_dag_to_test()
    dag.test()

    assert mock_log_hello_world.call_count == 2
    for call in mock_log_hello_world.calls:
        assert pattern.match(call.args[0]), call.args[0]
