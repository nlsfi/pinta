# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import functools
import typing

import pytest
from pinta_db.primary_db.models.management import ProductionArea
from pinta_e2e_utils import layers

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytestqt.qtbot import QtBot


@pytest.mark.xdist_group("airflow")
@pytest.mark.usefixtures("processed_production_areas", "reduce_point_cloud_tiles")
def test_reference_dem_workflow(
    qgis_plugin: "Plugin", qtbot: "QtBot", m_error_dialog: "MagicMock"
) -> None:
    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    assert production_area_layer.featureCount() == 1
    action = layers.find_layer_action(
        production_area_layer,
        ("Start reference DEM workflow", "Käynnistä vertausmallin työnkulku"),
    )

    feature = next(production_area_layer.getFeatures())
    layers.run_layer_action(production_area_layer, action, feature)

    def check_state(statuses: list[str]) -> None:
        production_area_layer.reload()
        updated_feature = next(production_area_layer.getFeatures())
        assert updated_feature["processing_status"] in statuses

    m_error_dialog.assert_not_called()
    qtbot.waitUntil(functools.partial(check_state, ["queued", "started"]), timeout=5000)
    qtbot.waitUntil(functools.partial(check_state, ["completed"]), timeout=40000)
