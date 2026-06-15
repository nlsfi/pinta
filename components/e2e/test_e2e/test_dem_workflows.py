# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import functools
import typing

import pytest
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models.management import ProductionArea
from pinta_e2e_utils import layers
from pinta_e2e_utils.airflow_client import AirflowClient, DagRun
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytestqt.qtbot import QtBot

PROCESSING_STATUS_TIMEOUT_MS = 90000


@pytest.mark.xdist_group("airflow")
@pytest.mark.usefixtures("processed_production_areas", "reduce_point_cloud_tiles")
def test_reference_dem_workflow(
    qgis_plugin: "Plugin",
    qtbot: "QtBot",
    m_error_dialog: "MagicMock",
    airflow_client: "AirflowClient",
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    assert production_area_layer.featureCount() == 1
    action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_START_REFERENCE_DEM_WORKFLOW,
    )

    feature = next(production_area_layer.getFeatures())

    client = api_client.get_api_client()
    with qtbot.waitSignal(client.workflow_started, timeout=10000) as blocker:
        layers.run_layer_action(production_area_layer, action, feature)
        dag_id, dag_run_id = blocker.args

    m_error_dialog.assert_not_called()
    dag_run = DagRun(id=dag_id, run_id=dag_run_id)

    def check_state(statuses: list[str]) -> None:
        production_area_layer.reload()
        updated_feature = next(production_area_layer.getFeatures())
        assert updated_feature["processing_status"] in statuses

    qtbot.waitUntil(functools.partial(check_state, ["queued", "started"]), timeout=5000)
    try:
        qtbot.waitUntil(
            functools.partial(check_state, ["completed"]),
            timeout=PROCESSING_STATUS_TIMEOUT_MS,
        )
    except QtBotTimeoutError:
        state = airflow_client.get_dag_run(dag_run).state
        pytest.fail(
            f"processing_status never reached 'completed' (dag run state={state})\n"
            f"{airflow_client.describe_failed_run(dag_run)}"
        )

    # Check that production area layers can be added
    completed_feature = next(production_area_layer.getFeatures())
    open_action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_OPEN_PRODUCTION_AREA_LAYERS,
    )
    layers.run_layer_action(production_area_layer, open_action, completed_feature)

    assert layers.get_raster_layer_by_model(reference.Dem)
    assert layers.get_vector_layer_by_model(reference.DiffPolygon)
    assert layers.get_vector_layer_by_model(reference.DiffPolygonCluster)
