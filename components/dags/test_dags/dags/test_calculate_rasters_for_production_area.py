# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING

import pytest
from airflow.dag_processing import dagbag
from airflow.models import DagBag

from pinta_dags.dags import calculate_rasters_for_production_area as rasters_dag

if TYPE_CHECKING:
    from airflow.sdk import DAG


def create_dag_to_test() -> "DAG":
    dag = rasters_dag.create_calculate_rasters_for_production_area_dag(
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


def test_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "ensure_job_database",
        "should_calculate_reference_dem",
        "should_calculate_dem_diff",
        "should_initialize_dem_preview",
        "should_suggest_masked_update_areas",
        "trigger_calculate_reference_dem",
        "trigger_calculate_dem_diff",
        "trigger_initialize_dem_preview",
        "trigger_suggest_masked_update_areas",
        "set_processing_status_completed",
        "set_processing_status_failed",
    }


def test_initialize_dem_preview_param_defaults_true() -> None:
    dag = create_dag_to_test()

    assert dag.params["initialize_dem_preview"] is True


def test_dem_preview_runs_in_parallel_off_ensure_database() -> None:
    # The DEM preview trigger is gated by its own short-circuit and hangs
    # directly off ensure_database, independent of the reference DEM -> diff
    # chain.
    dag = create_dag_to_test()

    ensure_database = dag.get_task("ensure_job_database")
    preview_gate = dag.get_task("should_initialize_dem_preview")
    trigger_preview = dag.get_task("trigger_initialize_dem_preview")

    assert ensure_database.task_id in preview_gate.upstream_task_ids
    assert preview_gate.task_id in trigger_preview.upstream_task_ids
    # Not chained behind the reference DEM / diff triggers.
    assert "trigger_calculate_reference_dem" not in trigger_preview.upstream_task_ids
    assert "trigger_calculate_dem_diff" not in trigger_preview.upstream_task_ids


def test_masked_update_areas_run_after_reference_dem_parallel_to_the_diff() -> None:
    # The suggestions read the freshly calculated reference DEM, but nothing
    # the DEM diff produces, so the two chains run side by side.
    dag = create_dag_to_test()

    mask_gate = dag.get_task("should_suggest_masked_update_areas")
    trigger_masks = dag.get_task("trigger_suggest_masked_update_areas")

    assert "trigger_calculate_reference_dem" in mask_gate.upstream_task_ids
    assert mask_gate.task_id in trigger_masks.upstream_task_ids
    assert "trigger_calculate_dem_diff" not in trigger_masks.upstream_task_ids
    # Runs even when the reference DEM trigger was skipped, like the DEM diff.
    assert mask_gate.trigger_rule == "none_failed"


def test_suggest_masked_update_areas_param_defaults_true() -> None:
    dag = create_dag_to_test()

    assert dag.params["suggest_masked_update_areas"] is True


def test_trigger_operators_poll_frequently_for_completion() -> None:
    # The waiting triggers must poll well below the 60 s default, otherwise the
    # orchestration sits idle for up to a minute after each child DAG finishes
    # and the end-to-end run times out.
    dag = create_dag_to_test()

    for task_id in (
        "trigger_calculate_reference_dem",
        "trigger_calculate_dem_diff",
        "trigger_initialize_dem_preview",
        "trigger_suggest_masked_update_areas",
    ):
        trigger = dag.get_task(task_id)
        assert trigger.wait_for_completion is True
        assert trigger.poke_interval <= 10


def test_status_tasks_wait_for_dem_preview_trigger() -> None:
    dag = create_dag_to_test()

    trigger_preview = dag.get_task("trigger_initialize_dem_preview")
    status_completed = dag.get_task("set_processing_status_completed")
    status_failed = dag.get_task("set_processing_status_failed")

    assert trigger_preview.task_id in status_completed.upstream_task_ids
    assert trigger_preview.task_id in status_failed.upstream_task_ids
