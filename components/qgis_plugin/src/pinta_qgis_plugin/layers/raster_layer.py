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

import logging

from qgis.core import QgsRasterLayer

from pinta_qgis_plugin.config import database
from pinta_qgis_plugin.exceptions import LayerCreationError
from pinta_qgis_plugin.layers import styles
from pinta_qgis_plugin.layers.config import BasemapLayerConfig, RasterModelLayerConfig

LOGGER = logging.getLogger(__name__)


def _create_qgs_raster_layer(
    uri_string: str, name: str, provider: str
) -> QgsRasterLayer:
    return QgsRasterLayer(uri_string, name, provider)


def create_raster_layer(config: BasemapLayerConfig, provider: str) -> QgsRasterLayer:
    """Create raster layer."""
    layer = _create_qgs_raster_layer(config.uri_string, config.layer_name, provider)
    if not layer.isValid():
        LOGGER.error("Uri of the invalid layer %s", layer.source())
        raise LayerCreationError(config.layer_name)
    return layer


def create_postgis_raster_layer(
    config: RasterModelLayerConfig, provider: str
) -> QgsRasterLayer:
    """Create a PostGIS raster layer from a database model configuration."""
    uri = database.get_database_uri()
    schema = config.db_model.__table_args__.get("schema")
    table_name = config.db_model.__tablename__
    uri.setDataSource(schema, table_name, config.rast_column)

    layer = _create_qgs_raster_layer(uri.uri(), config.layer_name, provider)
    if not layer.isValid():
        LOGGER.error("Uri of the invalid layer %s", layer.source())
        raise LayerCreationError(config.layer_name)

    if config.style_path is not None:
        styles.apply_style(layer, config.style_path)

    return layer
