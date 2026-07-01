# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import functools
import typing

import pytest
import sqlmodel
from pinta_common import constants
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils
from pinta_e2e_utils import layers
from pinta_e2e_utils.airflow_client import AirflowClient, DagRun
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytestqt.qtbot import QtBot
    from sqlmodel import Session

# The orchestration runs the reference DEM and DEM diff DAGs sequentially, each
# spinning up several short-lived task containers, so allow a generous budget.
PROCESSING_STATUS_TIMEOUT_MS = 240000
WORKFLOW_TIMEOUT_S = 240.0


def _get_production_area(db: "Session") -> ProductionArea:
    db.expire_all()
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    return production_area


def _count_diff_rasters(database_name: str) -> int:
    """Count the diff raster tiles written to the job database."""
    credentials = db_utils.get_job_admin_credentials(database_name)
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return connection.execute(
            sqlmodel.text(
                "SELECT (SELECT count(*) FROM reference.diff_gt_threshold) "
                "+ (SELECT count(*) FROM reference.diff_lte_threshold)"
            )
        ).scalar_one()


@pytest.mark.xdist_group("airflow")
@pytest.mark.usefixtures("seeded_processing_dem")
def test_calculate_rasters_for_production_area_workflow(
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
    assert _count_diff_rasters(completed_feature["database_name"]) > 0

    cluster_layer = layers.get_vector_layer_by_model(reference.DiffPolygonCluster)
    assert cluster_layer.setSubsetString("")
    assert cluster_layer.featureCount() > 0


@pytest.mark.xdist_group("airflow")
@pytest.mark.usefixtures("reduce_point_cloud_tiles")
def test_calculate_rasters_reference_dem_only(
    db: "Session",
    airflow_client: "AirflowClient",
) -> None:
    production_area = _get_production_area(db)

    # Only the reference DEM is requested; the DEM diff trigger must be skipped.
    run = airflow_client.trigger_dag_run(
        constants.DAG_ID_CALCULATE_RASTERS_FOR_PRODUCTION_AREA,
        conf={
            "id": str(production_area.id),
            "calculate_reference_dem": True,
            "calculate_dem_diff": False,
        },
    )
    state = airflow_client.wait_for_dag_run(run, timeout=WORKFLOW_TIMEOUT_S)
    assert state == "success", (
        f"DAG run finished with state={state}\n"
        f"{airflow_client.describe_failed_run(run)}"
    )

    updated = _get_production_area(db)
    assert updated.processing_status == ProcessingStatus.COMPLETED
    assert updated.database_name is not None
    # The trigger stamps the timestamp whenever processing_status changes.
    assert updated.processing_status_last_updated is not None

    # The DEM diff branch was skipped, so no diff rasters are produced.
    assert _count_diff_rasters(updated.database_name) == 0
