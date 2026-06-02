# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import typing

import pytest
from pinta_db.primary_db.models.management import PointCloudTile, ProductionArea
from pinta_e2e_utils import layers
from pinta_e2e_utils.airflow_client import AirflowClient

if typing.TYPE_CHECKING:
    from pinta_qgis_plugin.plugin import Plugin

PRODUCTION_AREA_VARIABLE = "production_area_1"
SHA256_HEX_LENGTH = 64


@pytest.mark.xdist_group("airflow")
@pytest.mark.usefixtures("processed_production_areas")
def test_process_production_areas_dag_runs_real_docker_tasks(
    qgis_plugin: "Plugin",
    airflow_client: AirflowClient,
) -> None:
    stored_hash = airflow_client.get_variable_value(PRODUCTION_AREA_VARIABLE)
    assert stored_hash is not None, (
        f"Variable '{PRODUCTION_AREA_VARIABLE}' was not set by the DAG"
    )
    assert len(stored_hash) == SHA256_HEX_LENGTH, (
        f"Expected sha256 hex hash, got {stored_hash!r}"
    )

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    assert production_area_layer.featureCount() == 1

    point_cloud_layer = layers.get_vector_layer_by_model(PointCloudTile)
    assert point_cloud_layer.featureCount() == 18
