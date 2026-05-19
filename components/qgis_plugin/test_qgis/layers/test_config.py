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

import pytest
from pinta_db.primary_db.models.all import ProductionArea

from pinta_qgis_plugin.layers.config import BasemapLayerConfig, ModelLayerConfig


@pytest.fixture
def config_json(data_path: Path) -> Path:
    json_path = data_path / "layer_configs/basemap_config.json"
    assert json_path.exists()
    return json_path


@pytest.fixture
def parsed_config(config_json: Path) -> list[BasemapLayerConfig]:
    return BasemapLayerConfig.from_json(config_json)


def test_basemap_layer_config_can_parse_json_properly(
    parsed_config: list[BasemapLayerConfig],
):
    assert parsed_config == [
        BasemapLayerConfig(
            layer_name="OpenStreetMap",
            uri_parameters=BasemapLayerConfig.UriParameters(
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                crs=None,
                type="xyz",
                layers=None,
                format="image/png",
                dpiMode="7",
                tilePixelRatio=1,
                tileMatrixSet=None,
                styles=None,
                zmin=0,
                zmax=19,
            ),
            user_name=None,
            password=None,
        ),
        BasemapLayerConfig(
            layer_name="Your own basemap",
            uri_parameters=BasemapLayerConfig.UriParameters(
                url="https://your-wmts-service/wmts/1.0.0/WMTSCapabilities.xml",
                crs="EPSG:3067",
                type=None,
                layers="layername",
                format="image/png",
                dpiMode="7",
                tilePixelRatio=1,
                tileMatrixSet="ETRS-TM35FIN",
                styles="default",
                zmin=0,
                zmax=19,
            ),
            user_name=None,
            password=None,
        ),
    ]


def test_basemap_layer_config_can_create_proper_uri(
    parsed_config: list[BasemapLayerConfig],
):
    osm_config = parsed_config[0]
    osm_config.user_name = "user"
    osm_config.password = "password"

    assert osm_config.uri_string == (
        "ser='user' password='password' "
        "&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&type=xyz"
        "&format=image/png&dpiMode=7&tilePixelRatio=1&zmin=0&zmax=19"
    )


def test_model_layer_config_create_can_set_read_only():
    layer_config = ModelLayerConfig.create(
        db_model=ProductionArea,
        layer_name="Production area",
        layer_id="production_area",
        read_only=True,
    )

    assert layer_config.read_only is True
