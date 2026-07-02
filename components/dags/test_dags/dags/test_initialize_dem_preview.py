# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag, dagbag

from pinta_dags.dags import initialize_dem_preview

if TYPE_CHECKING:
    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = initialize_dem_preview.create_initialize_dem_preview_dag(
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


def test_initialize_dem_preview_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "get_database_name",
        "build_job_connection_uri_task",
        "find_production_area",
        "initialize_dem_tables",
        "copy_dem_preview",
        "merge_dem_staging_tables",
    }


def test_dependencies() -> None:
    dag = create_dag_to_test()
    assert dag is not None

    get_database_name = dag.get_task("get_database_name")
    build_job_connection_uri_task = dag.get_task("build_job_connection_uri_task")
    find_production_area = dag.get_task("find_production_area")
    initialize = dag.get_task("initialize_dem_tables")
    copy_dem_preview = dag.get_task("copy_dem_preview")
    merge_dem_staging_tables = dag.get_task("merge_dem_staging_tables")

    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    assert find_production_area.task_id in initialize.upstream_task_ids
    assert initialize.task_id in copy_dem_preview.upstream_task_ids
    assert copy_dem_preview.task_id in merge_dem_staging_tables.upstream_task_ids


def test_copies_from_primary_dem_to_dem_preview() -> None:
    # The preview copy reads the primary DEM table and writes the job database
    # DEM preview table.
    assert initialize_dem_preview.FROM_DB_SCHEMA == "dem"
    assert initialize_dem_preview.FROM_DB_TABLE == "dem"
    assert initialize_dem_preview.TO_DB_SCHEMA == "user_data"
    assert initialize_dem_preview.TO_DB_TABLE == "dem_preview"


def test_get_max_parallel_pipelines_reads_variable() -> None:
    assert initialize_dem_preview._get_max_parallel_pipelines() == 2


def test_get_max_parallel_pipelines_rejects_below_one(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_CALCULATE_REFERENCE_DEM_MAX_PARALLEL_PIPELINES", "0"
    )
    with pytest.raises(ValueError, match="must be at least 1"):
        initialize_dem_preview._get_max_parallel_pipelines()


def test_get_staging_tables_reads_variable() -> None:
    assert initialize_dem_preview._get_staging_tables() == 3


def test_get_staging_tables_rejects_negative(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CALCULATE_REFERENCE_DEM_STAGING_TABLES", "-1")
    with pytest.raises(ValueError, match="must be at least 0"):
        initialize_dem_preview._get_staging_tables()


def test_copy_dem_preview_builds_and_executes_pipeline(
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
    mock_pipelines_module.postgis_to_postgis.return_value = mock_pipeline
    mocker.patch.dict(
        "sys.modules",
        {"pinta_processing.pipelines": mock_pipelines_module},
    )

    dag = create_dag_to_test()
    copy_dem_preview = dag.get_task("copy_dem_preview").python_callable

    copy_dem_preview(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        tile_wkt="POINT (0 0)",
        staging_tables=3,
        from_schema="dem",
        from_table="dem",
        to_schema="user_data",
        to_table="dem_preview",
    )

    mock_pipelines_module.postgis_to_postgis.assert_called_once()
    kwargs = mock_pipelines_module.postgis_to_postgis.call_args.kwargs
    assert kwargs["from_schema"] == "dem"
    assert kwargs["from_table"] == "dem"
    assert kwargs["to_schema"] == "user_data"
    assert kwargs["to_table"] == "dem_preview"
    assert kwargs["tile_wkt"] == "POINT (0 0)"
    assert kwargs["staging_tables"] == 3
    mock_pipeline.execute.assert_called_once_with()
