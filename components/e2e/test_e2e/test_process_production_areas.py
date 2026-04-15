# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import sqlite3
import typing
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from airflow.models import DagBag
from airflow.models.dagbag import sync_bag_to_db
from pinta_dags.dags.process_production_areas import create_process_production_areas_dag
from qgis._core import QgsProject

if TYPE_CHECKING:
    from typing import Any

    from pinta_qgis_plugin.plugin import Plugin
    from pytest_mock import MockerFixture


_TEST_DATA_PATH = Path(__file__).parents[3] / "test_data" / "point_clouds"


@pytest.fixture
def mock_task_docker(
    mocker: "MockerFixture",
) -> "Any":
    """Replace @task.docker with a plain @task, dropping Docker-specific args."""
    from airflow.sdk import task  # noqa: PLC0415

    def _mock_docker(*d_args: "Any", **d_kwargs: "Any") -> Callable:
        def wrapper(func: Callable) -> Callable:
            return task()(func)

        return wrapper

    return mocker.patch.object(task, "docker", _mock_docker)


@pytest.fixture
def base_path_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store the point cloud base path as an Airflow Variable."""
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_POINT_CLOUD_BASE_PATH", str(_TEST_DATA_PATH))
    monkeypatch.setenv("AIRFLOW_VAR_PINTA_CONTAINER_BASE_PATH", str(_TEST_DATA_PATH))


def test_process_production_areas_dag_updates_qgis_layers(
    qgis_plugin: "Plugin",
    mock_task_docker: "Any",
    base_path_variable: None,
) -> None:
    dag_id = f"test_process_production_areas_{uuid.uuid4()}"
    dag = create_process_production_areas_dag(dag_id=dag_id)

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    sync_bag_to_db(dag_bag, "mock-dags", None)

    dag.test()

    from pinta_qgis_plugin.layers.collections.management_layer_collection import (  # noqa: PLC0415
        ManagementLayerCollection,
    )

    ManagementLayerCollection.get().add_to_project()

    management_layers = ManagementLayerCollection.get().find_layers()
    production_area_layers = [
        typing.cast("Any", layer)
        for layer in management_layers
        if "production" in layer.name().lower()
    ]

    assert len(production_area_layers) == 1
    assert production_area_layers[0].featureCount() == 1
    db_path = Path(os.environ["AIRFLOW_HOME"]) / "airflow.db"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT val FROM variable WHERE key = 'production_area_1'"
        ).fetchone()
    assert row is not None
    assert len(QgsProject.instance().mapLayers()) >= 2
