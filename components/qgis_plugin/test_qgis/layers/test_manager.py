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

from pinta_qgis_plugin.layers import manager
from pinta_qgis_plugin.layers.collections.management_layer_collection import (
    ManagementLayerCollection,
)


@pytest.fixture
def mock_management_layer_collection(mocker: MockerFixture) -> MagicMock:
    m_management_layer_collection = MagicMock(spec=ManagementLayerCollection)
    mocker.patch.object(
        ManagementLayerCollection,
        "get",
        autospec=True,
        return_value=m_management_layer_collection,
    )
    return m_management_layer_collection


def test_initialize_layers_should_initialize_all_layers(
    mock_management_layer_collection: MagicMock,
):
    manager.initialize_layers()
    mock_management_layer_collection.add_to_project.assert_called_once()


def test_remove_layers_should_remove_all_layers(
    mock_management_layer_collection: MagicMock,
):
    manager.remove_layers()
    mock_management_layer_collection.remove_from_project.assert_called_once()
