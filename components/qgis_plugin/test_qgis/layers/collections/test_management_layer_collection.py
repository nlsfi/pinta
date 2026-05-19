# Copyright (C) 2026 Pinta QGIS Plugin Contributors.
#
#
# This file is part of Pinta QGIS Plugin.
#
# Pinta QGIS Plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Pinta QGIS Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Pinta QGIS Plugin.  If not, see <https://www.gnu.org/licenses/>.

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsProject, QgsVectorLayer

from pinta_qgis_plugin.project.config import management_layers
from pinta_qgis_plugin.project.groups import management_layer_collection


@pytest.fixture
def layer_collection() -> management_layer_collection.ManagementLayerCollection:
    return management_layer_collection.ManagementLayerCollection()


@pytest.fixture
def production_area_layer(empty_multipolygon_layer: QgsVectorLayer) -> QgsVectorLayer:
    layer = empty_multipolygon_layer
    layer.setName("Production area")
    return layer


@pytest.fixture
def mock_qgs_project(mocker: MockerFixture) -> MagicMock:
    mock_project = MagicMock()
    mocker.patch.object(
        QgsProject,
        "instance",
        autospec=True,
        return_value=mock_project,
    )
    return mock_project


def test_add_to_project_with_valid_layer_adds_to_project(
    layer_collection: management_layer_collection.ManagementLayerCollection,
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    mocker.patch.object(
        management_layer_collection.vector_layer,
        "create_vector_layer",
        autospec=True,
        return_value=production_area_layer,
    )
    layer_collection.add_to_project()
    assert mock_qgs_project.addMapLayer.call_count == len(
        management_layers.VECTOR_LAYERS
    )
    mock_qgs_project.addMapLayer.assert_called_with(
        production_area_layer, addToLegend=True
    )


def test_add_to_project_adds_open_action_to_production_area_layer(
    layer_collection: management_layer_collection.ManagementLayerCollection,
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    mocker.patch.object(
        management_layer_collection.vector_layer,
        "create_vector_layer",
        autospec=True,
        return_value=production_area_layer,
    )
    mock_add_action = mocker.patch.object(
        management_layer_collection,
        "_add_open_production_area_layers",
        autospec=True,
    )

    layer_collection.add_to_project()

    mock_add_action.assert_called_once_with(production_area_layer)


def test_add_open_production_area_layers_configures_feature_action(
    mocker: MockerFixture,
):
    action_manager = mocker.MagicMock()
    action = mocker.MagicMock()
    attribute_table_config = mocker.MagicMock()
    attribute_table_config.ActionWidgetStyle.ButtonList = "button-list"
    layer = mocker.MagicMock()
    layer.actions.return_value = action_manager
    layer.attributeTableConfig.return_value = attribute_table_config
    mock_qgs_action = mocker.patch.object(
        management_layer_collection,
        "QgsAction",
        autospec=True,
    )
    mock_qgs_action.GenericPython = "generic-python"
    mock_qgs_action.return_value = action

    management_layer_collection._add_open_production_area_layers(layer)

    mock_qgs_action.assert_called_once_with(
        "generic-python",
        description="Add production area related layers to map",
        action="",
        icon=None,
        capture=True,
        shortTitle="Open production area",
        actionScopes=["Feature"],
    )
    command = action.setCommand.call_args.args[0]
    assert command is not None
    action_manager.addAction.assert_called_once_with(action)
    attribute_table_config.setActionWidgetVisible.assert_called_once_with(True)
    attribute_table_config.setActionWidgetStyle.assert_called_once_with("button-list")
    layer.setAttributeTableConfig.assert_called_once_with(attribute_table_config)


def test_remove_layers_removes_all_layers(
    production_area_layer: QgsVectorLayer,
    layer_collection: management_layer_collection.ManagementLayerCollection,
):
    production_area_layer.setCustomProperty(
        management_layer_collection.ManagementLayerCollection.COLLECTION_ID_KEY,
        management_layer_collection.ManagementLayerCollection.collection_id,
    )
    assert QgsProject.instance().addMapLayer(production_area_layer)

    layer_collection.remove_from_project()
    assert len(QgsProject.instance().mapLayers()) == 0
