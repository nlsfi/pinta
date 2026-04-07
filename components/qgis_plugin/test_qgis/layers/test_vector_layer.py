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

from pinta_qgis_plugin.layers import config, manager, vector_layer


@pytest.fixture
def mock_uri():
    uri = MagicMock()
    uri.uri.return_value = "postgres://test"
    return uri


@pytest.fixture
def production_area_layer(mocker: MockerFixture, mock_uri: MagicMock) -> QgsVectorLayer:
    fake_layer = QgsVectorLayer("MultiPolygon", "Production area", "memory")
    mocker.patch.object(
        vector_layer.database,
        "get_database_uri",
        autospec=True,
        return_value=mock_uri,
    )
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=fake_layer,
    )
    return fake_layer


@pytest.fixture
def mock_qgs_project(mocker: MockerFixture) -> MagicMock:
    mock_project = MagicMock()
    mocker.patch.object(
        vector_layer.QgsProject,
        "instance",
        autospec=True,
        return_value=mock_project,
    )
    return mock_project


def test_create_layer_with_valid_layer_returns_layer(
    mock_uri: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    result = vector_layer.create_vector_layer(config.PRODUCTION_AREA)

    assert result is production_area_layer
    mock_uri.setDataSource.assert_called_once_with(
        "management", "production_area", "geom"
    )
    mock_uri.setKeyColumn.assert_called_once_with("id")
    mock_uri.setWkbType.assert_called_once()
    mock_uri.setSrid.assert_called_once_with("3067")
    assert production_area_layer.readOnly


def test_create_layer_with_invalid_layer_raises_exception(
    mocker: MockerFixture,
):
    mock_layer = MagicMock()
    mock_layer.isValid.return_value = False
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=mock_layer,
    )

    with pytest.raises(vector_layer.LayerCreationError):
        vector_layer.create_vector_layer(config.PRODUCTION_AREA)

    mock_layer.setReadOnly.assert_not_called()


def test_initialize_layers_with_valid_layer_adds_to_project(
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
):
    mock_layer = MagicMock(spec=QgsVectorLayer)
    mocker.patch.object(
        vector_layer,
        "create_vector_layer",
        autospec=True,
        return_value=mock_layer,
    )

    manager.initialize_layers()

    assert mock_qgs_project.addMapLayer.call_count == len(config.VECTOR_LAYERS)
    mock_qgs_project.addMapLayer.assert_called_with(mock_layer, addToLegend=True)


def test_initialize_layers_with_exception_does_not_add_to_project(
    mocker: MockerFixture,
    mock_qgs_project: MagicMock,
):
    m_create_layer = mocker.patch.object(
        vector_layer,
        "create_vector_layer",
        autospec=True,
        side_effect=vector_layer.LayerCreationError("test_layer"),
    )

    manager.initialize_layers()

    m_create_layer.assert_called_once()
    mock_qgs_project.addMapLayer.assert_not_called()


def test_remove_layers_removes_all_layers(production_area_layer: QgsVectorLayer):
    assert QgsProject.instance().addMapLayer(production_area_layer)

    vector_layer.remove_vector_layers()
    assert len(QgsProject.instance().mapLayers()) == 0
