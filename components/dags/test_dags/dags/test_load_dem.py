# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from airflow.dag_processing import dagbag
from airflow.models import DagBag
from airflow.sdk import task

from pinta_dags.dags import load_dem

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = load_dem.load_dem_dag(dag_id=f"some_id_{uuid.uuid4()}")

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag()
    dag_bag.bag_dag(dag)
    dagbag.sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_LOAD_DEM_MAX_PARALLEL_PIPELINES", "2")
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_LOAD_DEM_STAGING_TABLES", "3")


@pytest.fixture
def mock_task(
    mocker: "MockerFixture",
) -> "MagicMock":
    return mocker.patch(
        "pinta_dags.dags.load_dem.task",
        wraps=task,
    )


def test_load_dem_dag_all_tasks(
    mock_task: "MagicMock",
) -> None:
    create_dag_to_test()

    assert mock_task.call_count == 1
    assert mock_task.docker.call_count == 5


def test_load_dem_dag_runs_workflow(
    tmp_path: Path,
    monkeypatch: "pytest.MonkeyPatch",
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    (tmp_path / "dem_1.zip").write_text("fake zip data")
    (tmp_path / "dem_2.zip").write_text("fake zip data")
    (tmp_path / "ignored.tif").write_text("fake tif data")

    mock_raster = mock_submodule("pinta_db_utils.postgis.raster")
    mock_raster.DEFAULT_OVERVIEW_LEVELS = [2, 8]
    mock_raster.OVERVIEW_TABLE_NAME = "o_{level}_{table_name}"
    mock_pipeline = mocker.MagicMock()
    mock_pipelines_module = mock_submodule("pinta_processing.pipelines")
    mock_pipelines_module.rasterio_to_postgis.return_value = mock_pipeline

    dag = create_dag_to_test()
    dag.test(run_conf={"folder": str(tmp_path)})

    mock_raster.initialize_raster_table.assert_called_once_with(
        mocker.ANY, "dem", "dem", staging_tables=3
    )
    mock_raster.initialize_overview_tables.assert_called_once_with(
        mocker.ANY, "dem", "dem", staging_tables=3
    )
    assert mock_pipelines_module.rasterio_to_postgis.call_count == 2
    input_paths = {
        call.kwargs["input_path"]
        for call in mock_pipelines_module.rasterio_to_postgis.call_args_list
    }
    assert input_paths == {
        tmp_path / "dem_1.zip",
        tmp_path / "dem_2.zip",
    }
    for call in mock_pipelines_module.rasterio_to_postgis.call_args_list:
        assert call.kwargs["staging_tables"] == 3
    assert mock_pipeline.execute.call_count == 2
    assert mock_raster.merge_staging_tables.call_count == 3
    for call in mock_raster.merge_staging_tables.call_args_list:
        assert call.kwargs["staging_tables"] == 3
    mock_raster.truncate_raster_table.assert_not_called()


def test_load_dem_dag_truncates_tables_when_override_data(
    tmp_path: Path,
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    (tmp_path / "dem_1.zip").write_text("fake zip data")

    mock_raster = mock_submodule("pinta_db_utils.postgis.raster")
    mock_raster.DEFAULT_OVERVIEW_LEVELS = [2, 8]
    mock_raster.OVERVIEW_TABLE_NAME = "o_{level}_{table_name}"
    mock_pipelines_module = mock_submodule("pinta_processing.pipelines")
    mock_pipelines_module.rasterio_to_postgis.return_value = mocker.MagicMock()

    dag = create_dag_to_test()
    dag.test(run_conf={"folder": str(tmp_path), "override_data": True})

    truncated_tables = [
        call.args[2] for call in mock_raster.truncate_raster_table.call_args_list
    ]
    assert truncated_tables == ["dem", "o_2_dem", "o_8_dem"]
    assert mock_pipelines_module.rasterio_to_postgis.call_count == 1


def test_load_dem_dag_skips_processing_when_no_files(
    tmp_path: Path,
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    (tmp_path / "ignored.tif").write_text("fake tif data")

    mock_raster = mock_submodule("pinta_db_utils.postgis.raster")
    mock_pipelines_module = mock_submodule("pinta_processing.pipelines")

    dag = create_dag_to_test()
    dag.test(run_conf={"folder": str(tmp_path)})

    mock_raster.initialize_raster_table.assert_not_called()
    mock_raster.initialize_overview_tables.assert_not_called()
    mock_pipelines_module.rasterio_to_postgis.assert_not_called()
    mock_raster.merge_staging_tables.assert_not_called()


def test_load_dem_dag_does_not_truncate_when_no_files(
    tmp_path: Path,
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    (tmp_path / "ignored.tif").write_text("fake tif data")

    mock_raster = mock_submodule("pinta_db_utils.postgis.raster")
    mock_submodule("pinta_processing.pipelines")

    dag = create_dag_to_test()
    dag.test(run_conf={"folder": str(tmp_path), "override_data": True})

    mock_raster.truncate_raster_table.assert_not_called()
