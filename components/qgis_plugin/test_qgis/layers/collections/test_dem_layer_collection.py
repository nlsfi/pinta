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
from qgis.core import QgsProject, QgsRasterLayer

from pinta_qgis_plugin.layers import config
from pinta_qgis_plugin.layers.collections import dem_layer_collection


@pytest.fixture
def layer_collection() -> dem_layer_collection.DemLayerCollection:
    return dem_layer_collection.DemLayerCollection()


@pytest.fixture
def dem_layer(empty_raster_layer: QgsRasterLayer) -> QgsRasterLayer:
    layer = empty_raster_layer
    layer.setName("Elevation model")
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
    layer_collection: dem_layer_collection.DemLayerCollection,
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
    dem_layer: QgsRasterLayer,
):
    mocker.patch.object(
        dem_layer_collection.raster_layer,
        "create_postgis_raster_layer",
        autospec=True,
        return_value=dem_layer,
    )
    layer_collection.add_to_project()
    assert mock_qgs_project.addMapLayer.call_count == len(config.DEM_LAYERS)
    mock_qgs_project.addMapLayer.assert_called_with(dem_layer, addToLegend=True)


def test_remove_layers_removes_all_layers(
    dem_layer: QgsRasterLayer,
    layer_collection: dem_layer_collection.DemLayerCollection,
):
    dem_layer.setCustomProperty(
        dem_layer_collection.DemLayerCollection.COLLECTION_ID_KEY,
        dem_layer_collection.DemLayerCollection.collection_id,
    )
    assert QgsProject.instance().addMapLayer(dem_layer)

    layer_collection.remove_from_project()
    assert len(QgsProject.instance().mapLayers()) == 0
