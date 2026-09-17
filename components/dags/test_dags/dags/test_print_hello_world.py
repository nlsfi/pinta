# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import json
import re
import uuid
from typing import TYPE_CHECKING

import pytest
from airflow.dag_processing.dagbag import sync_bag_to_db
from airflow.models import DagBag
from airflow.sdk import task
from pinta_common import feature_flag_registry, flags

from pinta_dags.dags.print_hello_world import create_print_hello_world_dag

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from unittest.mock import MagicMock

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = create_print_hello_world_dag(dag_id=f"some_id_{uuid.uuid4()}")

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag()
    dag_bag.bag_dag(dag)
    sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")


@pytest.fixture
def set_print_current_time_flag(
    tmp_path: "Path", monkeypatch: "pytest.MonkeyPatch"
) -> "Callable[[bool], None]":
    config_file = tmp_path / "feature_flags.json"

    def _set(enabled: bool) -> None:
        content = {flags.FLAG_TEST_DAG_PRINT_CURRENT_TIME.name: {"enabled": enabled}}
        config_file.write_text(json.dumps(content), encoding="utf-8")
        registry = feature_flag_registry.FeatureFlagRegistry(config_file, ttl=0)
        monkeypatch.setattr(feature_flag_registry, "_registry", registry)

    return _set


@pytest.fixture
def mock_log_hello_world(
    mock_submodule: "Callable[[str], MagicMock]",
) -> "MagicMock":
    return mock_submodule("pinta_processing.scripts.hello_world").log_hello_world


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


@pytest.mark.parametrize("print_current_time", [True, False])
def test_print_hello_world_dag_runs_workflow_log_call(
    mock_log_hello_world: "MagicMock",
    set_print_current_time_flag: "Callable[[bool], None]",
    print_current_time: bool,
):
    set_print_current_time_flag(print_current_time)
    time_suffix = (
        r" at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00"
        if print_current_time
        else ""
    )
    pattern = re.compile(rf"^postgresql(?:\+psycopg)?://mockaddr:123/db{time_suffix}")

    dag = create_dag_to_test()
    dag.test()

    assert mock_log_hello_world.call_count == 2
    for call in mock_log_hello_world.call_args_list:
        assert pattern.fullmatch(call.args[0]), call.args[0]
        assert call.kwargs == {"name": "World"}
