# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING

import pytest
from airflow.dag_processing import dagbag
from airflow.models import DagBag

from pinta_dags.dags import calculate_dem_diff

if TYPE_CHECKING:
    from airflow.sdk import DAG


def create_dag_to_test() -> "DAG":
    dag = calculate_dem_diff.create_calculate_dem_diff_dag(
        dag_id=f"some_id_{uuid.uuid4()}"
    )

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag()
    dag_bag.bag_dag(dag)
    dagbag.sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB_ADMIN", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_CALCULATE_DEM_DIFF_MAX_PARALLEL_PIPELINES", "2"
    )
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CALCULATE_DEM_DIFF_STAGING_TABLES", "3")


def test_calculate_dem_diff_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "get_database_name",
        "build_job_connection_uri_task",
        "find_production_area",
        "initialize_diff_tables",
        "initialize_diff_lte_threshold_tables",
        "calculate_dem_diff",
        "merge_diff_tables",
        "merge_diff_lte_threshold_tables",
        "should_cluster",
        "cluster_diff_polygons",
    }


def test_dependencies() -> None:
    dag = create_dag_to_test()
    assert dag is not None

    get_database_name = dag.get_task("get_database_name")
    build_job_connection_uri_task = dag.get_task("build_job_connection_uri_task")
    find_production_area = dag.get_task("find_production_area")
    init_diff = dag.get_task("initialize_diff_tables")
    init_diff_lte = dag.get_task("initialize_diff_lte_threshold_tables")
    calculate = dag.get_task("calculate_dem_diff")
    merge_diff = dag.get_task("merge_diff_tables")
    merge_diff_lte = dag.get_task("merge_diff_lte_threshold_tables")
    should_cluster = dag.get_task("should_cluster")
    cluster = dag.get_task("cluster_diff_polygons")

    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    # The diff tiles come from the production area geometries task.
    assert find_production_area.task_id in init_diff.upstream_task_ids
    assert find_production_area.task_id in init_diff_lte.upstream_task_ids
    assert init_diff.task_id in calculate.upstream_task_ids
    assert init_diff_lte.task_id in calculate.upstream_task_ids
    assert calculate.task_id in merge_diff.upstream_task_ids
    assert calculate.task_id in merge_diff_lte.upstream_task_ids
    assert merge_diff.task_id in should_cluster.upstream_task_ids
    assert merge_diff_lte.task_id in should_cluster.upstream_task_ids
    assert should_cluster.task_id in cluster.upstream_task_ids


def test_get_max_parallel_pipelines_rejects_below_one(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_CALCULATE_DEM_DIFF_MAX_PARALLEL_PIPELINES", "0"
    )
    with pytest.raises(ValueError, match="must be at least 1"):
        calculate_dem_diff._get_max_parallel_pipelines()


def test_get_staging_tables_rejects_negative(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CALCULATE_DEM_DIFF_STAGING_TABLES", "-1")
    with pytest.raises(ValueError, match="must be at least 0"):
        calculate_dem_diff._get_staging_tables()
