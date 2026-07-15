# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag, dagbag
from pinta_common import constants

from pinta_dags.dags import register_update_areas

if TYPE_CHECKING:
    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = register_update_areas.create_register_update_areas_dag(
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
        "AIRFLOW_VAR_PINTA_REGISTER_UPDATE_AREAS_MAX_PARALLEL_PIPELINES", "2"
    )


def test_register_update_areas_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "set_processing_status_started",
        "get_database_name",
        "build_job_connection_uri_task",
        "find_dirty_update_areas",
        "should_dissolve",
        "trigger_dissolve_update_areas",
        "find_update_area_geometries",
        "register_update_area",
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
    should_dissolve = dag.get_task("should_dissolve")
    trigger_dissolve = dag.get_task("trigger_dissolve_update_areas")
    find_update_area_geometries = dag.get_task("find_update_area_geometries")
    register_update_area = dag.get_task("register_update_area")

    assert status_started.task_id in get_database_name.upstream_task_ids
    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    assert (
        build_job_connection_uri_task.task_id
        in find_dirty_update_areas.upstream_task_ids
    )
    # Dirty areas gate the dissolve trigger, which runs before the register.
    assert find_dirty_update_areas.task_id in should_dissolve.upstream_task_ids
    assert should_dissolve.task_id in trigger_dissolve.upstream_task_ids
    assert trigger_dissolve.task_id in find_update_area_geometries.upstream_task_ids
    assert find_update_area_geometries.task_id in register_update_area.upstream_task_ids


def test_trigger_dissolve_configuration() -> None:
    dag = create_dag_to_test()

    trigger_dissolve = dag.get_task("trigger_dissolve_update_areas")
    assert trigger_dissolve.trigger_dag_id == constants.DAG_ID_DISSOLVE_UPDATE_AREAS
    assert trigger_dissolve.wait_for_completion is True

    # The register read runs also when the dissolve trigger was skipped
    # because every update area was already clean.
    find_update_area_geometries = dag.get_task("find_update_area_geometries")
    assert find_update_area_geometries.trigger_rule == "none_failed"


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
        "trigger_dissolve_update_areas",
        "find_update_area_geometries",
        "register_update_area",
    }
    assert expected_upstream <= status_completed.upstream_task_ids
    assert expected_upstream <= status_failed.upstream_task_ids

    assert status_completed.trigger_rule == "none_failed"
    assert status_failed.trigger_rule == "one_failed"


def test_should_dissolve_gates_on_dirty_areas() -> None:
    dag = create_dag_to_test()
    should_dissolve = dag.get_task("should_dissolve").python_callable

    assert should_dissolve(dirty_update_areas=[]) is False
    assert (
        should_dissolve(
            dirty_update_areas=[
                {
                    "update_area_id": "00000000-0000-0000-0000-000000000000",
                    "geom_wkt": "POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))",
                }
            ]
        )
        is True
    )


def test_register_update_area_builds_and_executes_pipeline(
    mocker: "MockerFixture",
) -> None:
    from shapely import wkt as shapely_wkt

    mocker.patch("sqlalchemy.create_engine")
    mocker.patch("sqlmodel.Session")
    # Inject a mock pipelines module so the task body's ``from pinta_processing
    # import pipelines`` resolves to the mock instead of importing the real
    # module (which would load heavy DB modules and leak into the sys.modules
    # patching other DAG tests rely on).
    mock_pipeline = MagicMock()
    mock_pipelines_module = MagicMock()
    mock_pipelines_module.REGISTER_UPDATE_AREA_BUFFER = 6
    mock_pipelines_module.postgis_to_postgis.return_value = mock_pipeline
    mocker.patch.dict(
        "sys.modules",
        {"pinta_processing.pipelines": mock_pipelines_module},
    )

    dag = create_dag_to_test()
    register_update_area = dag.get_task("register_update_area").python_callable

    geom_wkt = "POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))"
    register_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        geom_wkt=geom_wkt,
        from_schema="user_data",
        from_table="dem_preview",
        to_schema="dem",
        to_table="dem",
    )

    mock_pipelines_module.postgis_to_postgis.assert_called_once()
    kwargs = mock_pipelines_module.postgis_to_postgis.call_args.kwargs
    assert kwargs["from_schema"] == "user_data"
    assert kwargs["from_table"] == "dem_preview"
    assert kwargs["to_schema"] == "dem"
    assert kwargs["to_table"] == "dem"
    assert kwargs["staging_tables"] == 0
    assert kwargs["mode"] == "update"
    assert "from_session" in kwargs
    assert "to_session" in kwargs

    # The update area WKT is buffered past the interpolated seam before the read.
    read_area = shapely_wkt.loads(kwargs["tile_wkt"])
    expected = shapely_wkt.loads(geom_wkt).buffer(
        mock_pipelines_module.REGISTER_UPDATE_AREA_BUFFER
    )
    assert read_area.symmetric_difference(expected).area < 1e-6

    mock_pipeline.execute.assert_called_once_with()
