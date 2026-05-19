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

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pinta_db.primary_db.models.dem import Dem
from pytest_mock import MockerFixture
from qgis.core import QgsDataSourceUri, QgsRasterLayer

from pinta_qgis_plugin.layers import config, raster_layer
from pinta_qgis_plugin.project.config import background_layers

PROVIDER = "postgresraster"


@pytest.fixture
def mock_uri() -> MagicMock:
    uri = MagicMock()
    uri.uri.return_value = "postgresraster://test"
    return uri


@pytest.fixture
def dem_raster_layer(
    mocker: MockerFixture,
    mock_uri: MagicMock,
    empty_raster_layer: QgsRasterLayer,
) -> QgsRasterLayer:
    fake_layer = empty_raster_layer
    fake_layer.setName("Elevation model")
    mocker.patch.object(
        raster_layer,
        "_create_qgs_raster_layer",
        autospec=True,
        return_value=fake_layer,
    )
    mocker.patch.object(
        QgsRasterLayer,
        "isValid",
        return_value=True,
    )
    return fake_layer


def test_create_postgis_raster_layer_returns_layer(
    mock_uri: MagicMock,
    dem_raster_layer: QgsRasterLayer,
):
    result = raster_layer.create_postgis_raster_layer(
        background_layers.DEM_LAYER, PROVIDER, mock_uri
    )
    assert result is dem_raster_layer


def test_create_postgis_raster_layer_sets_data_source(
    mock_uri: MagicMock,
    dem_raster_layer: QgsRasterLayer,
):
    raster_layer.create_postgis_raster_layer(
        background_layers.DEM_LAYER, PROVIDER, mock_uri
    )
    mock_uri.setDataSource.assert_called_once_with("dem", "dem", "rast")


def test_create_postgis_raster_layer_uses_provided_uri(
    mock_uri: MagicMock,
    dem_raster_layer: QgsRasterLayer,
):
    raster_layer.create_postgis_raster_layer(
        background_layers.DEM_LAYER,
        PROVIDER,
        mock_uri,
    )

    raster_layer._create_qgs_raster_layer.assert_called_once_with(
        mock_uri.uri.return_value, background_layers.DEM_LAYER.layer_name, PROVIDER
    )


def test_create_postgis_raster_layer_sets_layer_id(dem_raster_layer: QgsRasterLayer):
    uri = MagicMock(spec=QgsDataSourceUri)
    uri.uri.return_value = "postgresraster://test"
    raster_layer.create_postgis_raster_layer(background_layers.DEM_LAYER, PROVIDER, uri)
    assert (
        dem_raster_layer.customProperty(config.PINTA_LAYER_ID)
        == background_layers.DEM_LAYER.layer_id
    )


def test_create_postgis_raster_layer_applies_style(
    mocker: MockerFixture,
    mock_uri: MagicMock,
    dem_raster_layer: QgsRasterLayer,
):
    mock_apply = mocker.patch.object(raster_layer.styles, "apply_style")
    raster_layer.create_postgis_raster_layer(
        background_layers.DEM_LAYER, PROVIDER, mock_uri
    )
    mock_apply.assert_called_once_with(
        dem_raster_layer, background_layers.DEM_LAYER.style_path
    )


def test_create_postgis_raster_layer_with_invalid_layer_raises_exception(
    mocker: MockerFixture,
):
    mock_layer = MagicMock()
    mock_layer.isValid.return_value = False
    mocker.patch.object(
        raster_layer,
        "_create_qgs_raster_layer",
        autospec=True,
        return_value=mock_layer,
    )

    with pytest.raises(raster_layer.LayerCreationError):
        raster_layer.create_postgis_raster_layer(
            background_layers.DEM_LAYER,
            PROVIDER,
            MagicMock(spec=QgsDataSourceUri),
        )


def test_create_postgis_raster_layer_without_style_skips_apply(
    mocker: MockerFixture,
    mock_uri: MagicMock,
    empty_raster_layer: QgsRasterLayer,
):
    config_no_style = config.RasterModelLayerConfig.create(
        db_model=Dem,
        layer_name="No style",
        layer_id="no_style",
        style_path=None,
    )
    fake_layer = empty_raster_layer
    mocker.patch.object(
        QgsRasterLayer,
        "isValid",
        return_value=True,
    )
    mocker.patch.object(
        raster_layer, "_create_qgs_raster_layer", autospec=True, return_value=fake_layer
    )
    mock_apply = mocker.patch.object(raster_layer.styles, "apply_style", autospec=True)

    raster_layer.create_postgis_raster_layer(config_no_style, PROVIDER, mock_uri)

    mock_apply.assert_not_called()


def test_raster_model_layer_config_create_derives_schema_and_table():
    layer_config = config.RasterModelLayerConfig.create(
        db_model=Dem,
        layer_name="Test",
        layer_id="test",
    )
    assert layer_config.schema == "dem"
    assert layer_config.table_name == "dem"
    assert layer_config.rast_column == "rast"
    assert layer_config.style_path is None


def test_raster_model_layer_config_create_with_style_path():
    path = Path("/some/style.qml")
    layer_config = config.RasterModelLayerConfig.create(
        db_model=Dem,
        layer_name="Test",
        layer_id="test",
        style_path=path,
    )
    assert layer_config.style_path == path
