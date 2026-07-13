# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag, dagbag

from pinta_dags.dags import dissolve_update_areas

if TYPE_CHECKING:
    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = dissolve_update_areas.create_dissolve_update_areas_dag(
        dag_id=f"some_id_{uuid.uuid4()}"
    )

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    dagbag.sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB_ADMIN", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES", "2"
    )


def test_dissolve_update_areas_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "set_processing_status_started",
        "get_database_name",
        "build_job_connection_uri_task",
        "find_dirty_update_areas",
        "dissolve_update_area",
        "set_processing_status_completed",
        "set_processing_status_failed",
    }


def test_dependencies() -> None:
    dag = create_dag_to_test()
    assert dag is not None

    status_started = dag.get_task("set_processing_status_started")
    get_database_name = dag.get_task("get_database_name")
    build_job_connection_uri_task = dag.get_task("build_job_connection_uri_task")
    find_dirty_update_areas = dag.get_task("find_dirty_update_areas")
    dissolve_update_area = dag.get_task("dissolve_update_area")

    assert status_started.task_id in get_database_name.upstream_task_ids
    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    assert (
        build_job_connection_uri_task.task_id
        in find_dirty_update_areas.upstream_task_ids
    )
    assert find_dirty_update_areas.task_id in dissolve_update_area.upstream_task_ids


def test_processing_status_tasks() -> None:
    dag = create_dag_to_test()

    status_completed = dag.get_task("set_processing_status_completed")
    status_failed = dag.get_task("set_processing_status_failed")

    # Both terminal status tasks fan in from every step that can fail so the
    # status is always resolved, even when an early step fails.
    expected_upstream = {
        "set_processing_status_started",
        "get_database_name",
        "build_job_connection_uri_task",
        "find_dirty_update_areas",
        "dissolve_update_area",
    }
    assert expected_upstream <= status_completed.upstream_task_ids
    assert expected_upstream <= status_failed.upstream_task_ids

    assert status_completed.trigger_rule == "none_failed"
    assert status_failed.trigger_rule == "one_failed"


def test_get_max_parallel_pipelines_reads_variable() -> None:
    assert dissolve_update_areas._get_max_parallel_pipelines() == 2


def test_get_max_parallel_pipelines_rejects_below_one(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES", "0"
    )
    with pytest.raises(ValueError, match="must be at least 1"):
        dissolve_update_areas._get_max_parallel_pipelines()


def test_get_max_parallel_pipelines_defaults_when_unset(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.delenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES",
        raising=False,
    )
    assert dissolve_update_areas._get_max_parallel_pipelines() == 4


def test_dissolve_update_area_builds_and_executes_pipeline(
    mocker: "MockerFixture",
) -> None:
    mocker.patch("sqlalchemy.create_engine")
    mocker.patch("sqlmodel.Session")
    # Inject a mock pipelines module so the task body's ``from pinta_processing
    # import pipelines`` resolves to the mock instead of importing the real
    # module (which would load heavy DB modules and leak into the sys.modules
    # patching other DAG tests rely on).
    mock_pipeline = MagicMock()
    mock_pipelines_module = MagicMock()
    mock_pipelines_module.dissolve_update_area.return_value = mock_pipeline
    mocker.patch.dict(
        "sys.modules",
        {"pinta_processing.pipelines": mock_pipelines_module},
    )

    dag = create_dag_to_test()
    dissolve_update_area = dag.get_task("dissolve_update_area").python_callable

    dissolve_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
        geom_wkt="POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))",
    )

    mock_pipelines_module.dissolve_update_area.assert_called_once()
    kwargs = mock_pipelines_module.dissolve_update_area.call_args.kwargs
    assert kwargs["geom_wkt"] == "POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))"
    assert "primary_session" in kwargs
    assert "job_session" in kwargs
    mock_pipeline.execute.assert_called_once_with()


def test_dissolve_update_area_clears_dirty_flag(mocker: "MockerFixture") -> None:
    mocker.patch("sqlalchemy.create_engine")
    session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.return_value = session

    update_area = MagicMock(dirty=True)
    session.exec.return_value.first.return_value = update_area

    mock_pipelines_module = MagicMock()
    mocker.patch.dict(
        "sys.modules",
        {"pinta_processing.pipelines": mock_pipelines_module},
    )

    dag = create_dag_to_test()
    dissolve_update_area = dag.get_task("dissolve_update_area").python_callable

    dissolve_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
        geom_wkt="POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))",
    )

    # After a successful dissolve the worker marks the area clean and commits it.
    assert update_area.dirty is False
    session.add.assert_called_once_with(update_area)
    session.commit.assert_called_once_with()
