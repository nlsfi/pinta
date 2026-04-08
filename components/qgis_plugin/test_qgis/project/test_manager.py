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
import typing

import pytest
from pinta_db import env
from qgis.core import QgsProject

from pinta_qgis_plugin.layers.collections.basemap_layer_collection import (
    BasemapLayerCollection,
)
from pinta_qgis_plugin.layers.collections.management_layer_collection import (
    ManagementLayerCollection,
)
from pinta_qgis_plugin.project import manager

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture
    from qgis.gui import QgsMapCanvas


@pytest.fixture
def mock_management_layer_collection(mocker: "MockerFixture") -> "MagicMock":
    m_management_layer_collection = mocker.MagicMock(spec=ManagementLayerCollection)
    mocker.patch.object(
        ManagementLayerCollection,
        "get",
        autospec=True,
        return_value=m_management_layer_collection,
    )
    return m_management_layer_collection


@pytest.fixture
def mock_basemap_layer_collection(mocker: "MockerFixture") -> "MagicMock":
    mock_basemap_layer_collection = mocker.MagicMock(spec=BasemapLayerCollection)
    mocker.patch.object(
        BasemapLayerCollection,
        "get",
        autospec=True,
        return_value=mock_basemap_layer_collection,
    )
    return mock_basemap_layer_collection


def test_initialize_layers_should_initialize_all_layers(
    mock_management_layer_collection: "MagicMock",
    mock_basemap_layer_collection: "MagicMock",
    qgis_canvas: "QgsMapCanvas",
):
    initial_extent = qgis_canvas.extent()
    manager.initialize_project()
    mock_basemap_layer_collection.add_to_project.assert_called_once()
    mock_management_layer_collection.add_to_project.assert_called_once()
    assert QgsProject.instance().crs().authid() == f"EPSG:{env.SRID}"
    assert qgis_canvas.extent() != initial_extent


def test_remove_layers_should_remove_all_layers(
    mock_management_layer_collection: "MagicMock",
    mock_basemap_layer_collection: "MagicMock",
):
    manager.clean_project()
    mock_basemap_layer_collection.remove_from_project.assert_called_once()
    mock_management_layer_collection.remove_from_project.assert_called_once()
