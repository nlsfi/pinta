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
from qgis.core import QgsVectorLayer

from pinta_qgis_plugin.layers import config, manager


@pytest.fixture
def mock_uri():
    uri = MagicMock()
    uri.uri.return_value = "postgres://test"
    return uri


@pytest.fixture
def fake_layer(mocker: MockerFixture, mock_uri: MagicMock) -> QgsVectorLayer:
    fake_layer = QgsVectorLayer("MultiPolygon", "empty", "memory")
    mocker.patch.object(
        manager.database,
        "get_database_uri",
        autospec=True,
        return_value=mock_uri,
    )
    mocker.patch.object(
        manager,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=fake_layer,
    )
    return fake_layer


@pytest.fixture
def mock_qgs_project(mocker: MockerFixture) -> MagicMock:
    mock_project = MagicMock()
    mocker.patch.object(
        manager.QgsProject,
        "instance",
        autospec=True,
        return_value=mock_project,
    )
    return mock_project


def test_create_layer_with_valid_layer_returns_layer(
    mock_uri: MagicMock,
    fake_layer: QgsVectorLayer,
):
    result = manager.create_layer(config.PRODUCTION_AREA)

    assert result is fake_layer
    mock_uri.setDataSource.assert_called_once_with(
        "management", "production_area", "geom"
    )
    mock_uri.setKeyColumn.assert_called_once_with("id")
    mock_uri.setWkbType.assert_called_once()
    mock_uri.setSrid.assert_called_once_with("3067")
    assert fake_layer.readOnly


def test_create_layer_with_invalid_layer_raises_exception(
    mocker: MockerFixture,
):
    mock_layer = MagicMock()
    mock_layer.isValid.return_value = False
    mocker.patch.object(
        manager,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=mock_layer,
    )

    with pytest.raises(manager.LayerCreationError):
        manager.create_layer(config.PRODUCTION_AREA)

    mock_layer.setReadOnly.assert_not_called()


def test_initialize_layers_with_valid_layer_adds_to_project(
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
):
    mock_layer = MagicMock(spec=QgsVectorLayer)
    mocker.patch.object(
        manager,
        "create_layer",
        autospec=True,
        return_value=mock_layer,
    )

    manager.initialize_layers()

    assert mock_qgs_project.addMapLayer.call_count == len(config.LAYERS)
    mock_qgs_project.addMapLayer.assert_called_with(mock_layer, addToLegend=True)


def test_initialize_layers_with_exception_does_not_add_to_project(
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
):
    mocker.patch.object(
        manager,
        "create_layer",
        autospec=True,
        side_effect=manager.LayerCreationError("test_layer"),
    )

    manager.initialize_layers()

    assert manager.create_layer.call_count == 1  # type: ignore[attr-defined]
    mock_qgs_project.addMapLayer.assert_not_called()
