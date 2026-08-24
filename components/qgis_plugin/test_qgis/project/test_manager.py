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
from pinta_common import Settings
from qgis.core import QgsProject

from pinta_qgis_plugin.project import manager
from pinta_qgis_plugin.project.groups.basemap_layer_collection import (
    BasemapLayerCollection,
)
from pinta_qgis_plugin.project.groups.dem_layer_collection import (
    DemLayerCollection,
)
from pinta_qgis_plugin.project.groups.job_layer_collection import JobLayerCollection
from pinta_qgis_plugin.project.groups.management_layer_collection import (
    ManagementLayerCollection,
)

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
def mock_dem_layer_collection(mocker: "MockerFixture") -> "MagicMock":
    mock_dem = mocker.MagicMock(spec=DemLayerCollection)
    mocker.patch.object(
        DemLayerCollection,
        "get",
        autospec=True,
        return_value=mock_dem,
    )
    return mock_dem


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


@pytest.fixture
def mock_job_layer_collection(mocker: "MockerFixture") -> "MagicMock":
    mock_job = mocker.MagicMock(spec=JobLayerCollection)
    mocker.patch.object(
        JobLayerCollection,
        "get",
        autospec=True,
        return_value=mock_job,
    )
    return mock_job


@pytest.fixture
def mock_job_layer_cleanup(mocker: "MockerFixture") -> "MagicMock":
    return mocker.patch.object(
        JobLayerCollection,
        "remove_all_from_project",
        autospec=True,
    )


def test_initialize_layers_should_initialize_all_layers(
    mock_management_layer_collection: "MagicMock",
    mock_dem_layer_collection: "MagicMock",
    mock_basemap_layer_collection: "MagicMock",
    qgis_canvas: "QgsMapCanvas",
):
    initial_extent = qgis_canvas.extent()
    manager.initialize_project()
    mock_basemap_layer_collection.add_to_project.assert_called_once()
    mock_management_layer_collection.add_to_project.assert_called_once()
    assert QgsProject.instance().crs().authid() == f"EPSG:{Settings.DB_SRID}"
    assert qgis_canvas.extent() != initial_extent


def test_remove_layers_should_remove_all_layers(
    mock_management_layer_collection: "MagicMock",
    mock_dem_layer_collection: "MagicMock",
    mock_basemap_layer_collection: "MagicMock",
    mock_job_layer_cleanup: "MagicMock",
):
    manager.clean_project()
    mock_basemap_layer_collection.remove_from_project.assert_called_once()
    mock_dem_layer_collection.remove_from_project.assert_called_once()
    mock_management_layer_collection.remove_from_project.assert_called_once()
    mock_job_layer_cleanup.assert_called_once_with()


def test_open_production_area_adds_job_layers(
    mock_job_layer_collection: "MagicMock",
):
    manager.open_production_area("production_area_db", "group_name")

    mock_job_layer_collection.set_database_name.assert_called_once_with(
        "production_area_db"
    )
    mock_job_layer_collection.set_group_name.assert_called_once_with("group_name")
    mock_job_layer_collection.add_to_project.assert_called_once_with()


def test_close_production_area_removes_job_layers(
    mock_job_layer_collection: "MagicMock",
):
    manager.close_production_area("production_area_db")

    mock_job_layer_collection.set_database_name.assert_called_once_with(
        "production_area_db"
    )
    mock_job_layer_collection.remove_from_project.assert_called_once_with()
