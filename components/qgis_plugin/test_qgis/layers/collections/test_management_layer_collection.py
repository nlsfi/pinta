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
