# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING

import pytest
from airflow.models import DagBag, dagbag
from airflow.sdk import task

from pinta_dags.dags import calculate_reference_dem
from pinta_dags.dags.calculate_reference_dem import (
    build_job_connection_uri,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("base_uri", "database_name", "expected"),
    [
        (
            "postgresql+psycopg://user:pass@host:1234/template_db",
            "job_test",
            "postgresql+psycopg://user:pass@host:1234/job_test",
        ),
        (
            "postgresql://user:pass@host:1234/template_db",
            "job_test",
            "postgresql://user:pass@host:1234/job_test",
        ),
        (
            "postgresql://user:pass@host:1234/",
            "job_test",
            "postgresql://user:pass@host:1234/job_test",
        ),
        (
            "postgresql://user:pass@host:1234",
            "job_test",
            "postgresql://user:pass@host:1234/job_test",
        ),
        (
            "postgresql+psycopg://user:pass@host:1234/template_db",
            "job_82e59135-0a76-4460-b7fe-2e7a39796d6e",
            "postgresql+psycopg://user:pass@host:1234/job_82e59135-0a76-4460-b7fe-2e7a39796d6e",
        ),
    ],
)
def test_build_job_connection_uri(base_uri: str, database_name: str, expected: str):
    result = build_job_connection_uri(
        base_uri=base_uri,
        database_name=database_name,
    )

    assert result == expected


def create_dag_to_test() -> "DAG":
    dag = calculate_reference_dem.create_calculate_reference_dem_dag(
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
        "AIRFLOW_VAR_PINTA_CALCULATE_REFERENCE_DEM_MAX_PARALLEL_PIPELINES", "2"
    )
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CALCULATE_REFERENCE_DEM_STAGING_TABLES", "3")


@pytest.fixture
def mock_task(
    mocker: "MockerFixture",
) -> "MagicMock":
    return mocker.patch(
        "pinta_dags.dags.calculate_reference_dem.task",
        wraps=task,
    )


def test_calculate_reference_all_tasks(
    mock_task: "MagicMock",
) -> None:
    create_dag_to_test()

    assert mock_task.call_count == 1
    assert mock_task.docker.call_count == 7


def test_dependencies():
    dag = create_dag_to_test()
    assert dag is not None

    create_job_database = dag.get_task("create_job_database")
    find_production_area = dag.get_task("find_production_area")
    initialize = dag.get_task("initialize_dem_tables")
    blast2dem = dag.get_task("blast2dem")
    merge_dem_staging_tables = dag.get_task("merge_dem_staging_tables")

    assert create_job_database.task_id in find_production_area.upstream_task_ids
    assert find_production_area.task_id in initialize.upstream_task_ids
    assert find_production_area.task_id in blast2dem.upstream_task_ids
    assert initialize.task_id in blast2dem.upstream_task_ids
    assert blast2dem.task_id in merge_dem_staging_tables.upstream_task_ids
