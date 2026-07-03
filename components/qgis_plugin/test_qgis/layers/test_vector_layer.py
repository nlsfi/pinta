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
from qgis.core import QgsDataSourceUri, QgsVectorLayer

from pinta_qgis_plugin.layers import config, vector_layer
from pinta_qgis_plugin.project.config import management_layers

PROVIDER = "postgres"


@pytest.fixture
def mock_uri():
    uri = MagicMock()
    uri.uri.return_value = "postgres://test"
    return uri


@pytest.fixture
def production_area_layer(
    mocker: MockerFixture, mock_uri: MagicMock, empty_multipolygon_layer: QgsVectorLayer
) -> QgsVectorLayer:
    fake_layer = empty_multipolygon_layer
    fake_layer.setName("Production area")
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=fake_layer,
    )
    return fake_layer


def test_create_layer_with_valid_layer_returns_layer(
    mock_uri: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    result = vector_layer.create_vector_layer(
        management_layers.PRODUCTION_AREA, PROVIDER, mock_uri
    )

    assert result is production_area_layer
    mock_uri.setDataSource.assert_called_once_with(
        "management", "production_area", "geom"
    )
    mock_uri.setKeyColumn.assert_called_once_with("id")
    mock_uri.setWkbType.assert_called_once()
    mock_uri.setSrid.assert_called_once_with("3067")
    assert production_area_layer.readOnly() is True


def test_create_layer_honors_read_only_config(
    mock_uri: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    read_only_config = config.VectorLayerConfig(
        schema="management",
        table_name="production_area",
        layer_name="Production area",
        layer_id="production_area",
        key_column="id",
        wkb_type=management_layers.PRODUCTION_AREA.wkb_type,
        read_only=True,
    )

    vector_layer.create_vector_layer(read_only_config, PROVIDER, mock_uri)

    assert production_area_layer.readOnly() is True


def test_create_layer_uses_provided_uri(
    mock_uri: MagicMock,
    production_area_layer: QgsVectorLayer,
):
    vector_layer.create_vector_layer(
        management_layers.PRODUCTION_AREA, PROVIDER, mock_uri
    )

    vector_layer._create_qgs_vector_layer.assert_called_once_with(
        mock_uri, management_layers.PRODUCTION_AREA.layer_name, PROVIDER
    )


def test_create_layer_sets_layer_id(production_area_layer: QgsVectorLayer):
    uri = MagicMock(spec=QgsDataSourceUri)
    uri.uri.return_value = "postgres://test"
    vector_layer.create_vector_layer(management_layers.PRODUCTION_AREA, PROVIDER, uri)

    assert (
        production_area_layer.customProperty(config.PINTA_LAYER_ID)
        == management_layers.PRODUCTION_AREA.layer_id
    )


def test_create_layer_sets_field_aliases(mocker: MockerFixture, mock_uri: MagicMock):
    layer = QgsVectorLayer(
        "MultiPolygon?field=id:integer&field=name:string", "", "memory"
    )
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=layer,
    )
    layer_config = config.VectorLayerConfig(
        schema="management",
        table_name="production_area",
        layer_name="Production area",
        layer_id="production_area",
        key_column="id",
        wkb_type=management_layers.PRODUCTION_AREA.wkb_type,
        aliases={
            "id": "Identifier",
            "name": "Name",
            "missing": "Missing",
        },
    )

    vector_layer.create_vector_layer(layer_config, PROVIDER, mock_uri)

    assert layer.attributeAlias(layer.fields().lookupField("id")) == "Identifier"
    assert layer.attributeAlias(layer.fields().lookupField("name")) == "Name"


def test_create_layer_sets_value_maps(mocker: MockerFixture, mock_uri: MagicMock):
    layer = QgsVectorLayer(
        "MultiPolygon?field=id:integer&field=status:string", "", "memory"
    )
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=layer,
    )
    layer_config = config.VectorLayerConfig(
        schema="management",
        table_name="production_area",
        layer_name="Production area",
        layer_id="production_area",
        key_column="id",
        wkb_type=management_layers.PRODUCTION_AREA.wkb_type,
        value_maps=[
            config.ValueMapConfig(
                field_name="status",
                value_map={"Not started": "not_started", "Completed": "completed"},
            )
        ],
    )

    vector_layer.create_vector_layer(layer_config, PROVIDER, mock_uri)

    widget = layer.editorWidgetSetup(layer.fields().lookupField("status"))
    assert widget.type() == "ValueMap"
    assert widget.config() == {
        "map": [{"not_started": "Not started"}, {"completed": "Completed"}]
    }


def test_create_layer_sets_default_value_expressions(
    mocker: MockerFixture, mock_uri: MagicMock
):
    layer = QgsVectorLayer(
        "MultiPolygon?field=id:string&field=name:string", "", "memory"
    )
    mocker.patch.object(
        vector_layer,
        "_create_qgs_vector_layer",
        autospec=True,
        return_value=layer,
    )
    layer_config = config.VectorLayerConfig(
        schema="user_data",
        table_name="update_area",
        layer_name="Update area",
        layer_id="update_area",
        key_column="id",
        wkb_type=management_layers.PRODUCTION_AREA.wkb_type,
        default_expressions={"id": "uuid('WithoutBraces')"},
    )

    vector_layer.create_vector_layer(layer_config, PROVIDER, mock_uri)

    default_value = layer.defaultValueDefinition(layer.fields().lookupField("id"))
    assert default_value.expression() == "uuid('WithoutBraces')"


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
        vector_layer.create_vector_layer(
            management_layers.PRODUCTION_AREA,
            PROVIDER,
            MagicMock(spec=QgsDataSourceUri),
        )

    mock_layer.setReadOnly.assert_not_called()
