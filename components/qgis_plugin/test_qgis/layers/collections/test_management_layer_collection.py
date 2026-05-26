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


def test_add_to_project_adds_actions_to_production_area_layer(
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
    mock_add_open_action = mocker.patch.object(
        management_layer_collection,
        "_add_open_production_area_layers_action",
        autospec=True,
    )
    mock_add_dem_update_action = mocker.patch.object(
        management_layer_collection,
        "_add_start_reference_dem_workflow_action",
        autospec=True,
    )

    layer_collection.add_to_project()

    mock_add_open_action.assert_called_once_with(production_area_layer)
    mock_add_dem_update_action.assert_called_once_with(production_area_layer)


def test_add_open_production_area_layers_delegates_to_layer_utils(
    mocker: MockerFixture,
):
    layer = mocker.MagicMock()
    mock_add_action = mocker.patch.object(
        management_layer_collection.layer_utils,
        "add_action_to_vector_layer",
        autospec=True,
    )

    management_layer_collection._add_open_production_area_layers_action(layer)

    mock_add_action.assert_called_once()
    call = mock_add_action.call_args
    assert call.args == (layer,)
    assert call.kwargs["description"] == "Add production area related layers to map"
    assert call.kwargs["short_title"] == "Open production area"
    command = call.kwargs["command"]
    assert (
        "from pinta_qgis_plugin.project.manager import open_production_area" in command
    )
    assert "open_production_area(db_name, group_name)" in command
    assert "[%database_name%]" in command
    assert "[%name%]" in command


def test_add_start_reference_dem_processing_action_delegates_to_layer_utils(
    mocker: MockerFixture,
):
    layer = mocker.MagicMock()
    mock_add_action = mocker.patch.object(
        management_layer_collection.layer_utils,
        "add_action_to_vector_layer",
        autospec=True,
    )

    management_layer_collection._add_start_reference_dem_workflow_action(layer)

    mock_add_action.assert_called_once()
    call = mock_add_action.call_args
    assert call.args == (layer,)
    assert (
        call.kwargs["description"] == "Start reference DEM workflow for production area"
    )
    assert call.kwargs["short_title"] == "Start reference DEM workflow"
    command = call.kwargs["command"]
    assert "from pinta_qgis_plugin.workflows import dem" in command
    assert "dem.start_reference_dem_workflow(job_id)" in command
    assert "[%id%]" in command


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
