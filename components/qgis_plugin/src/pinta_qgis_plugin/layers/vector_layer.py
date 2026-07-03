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

from qgis.core import QgsDataSourceUri, QgsVectorLayer

from pinta_qgis_plugin.exceptions import LayerCreationError
from pinta_qgis_plugin.layers import styles, utils
from pinta_qgis_plugin.layers.config import (
    LAYER_ID_COLUMN,
    PINTA_LAYER_ID,
    VectorLayerConfig,
)

LOGGER = logging.getLogger(__name__)


def _create_qgs_vector_layer(
    uri: QgsDataSourceUri, name: str, provider: str
) -> QgsVectorLayer:
    return QgsVectorLayer(uri.uri(), name, provider)


def create_vector_layer(
    config: VectorLayerConfig, provider: str, uri: QgsDataSourceUri
) -> QgsVectorLayer:
    """Create vector layer from database model configuration."""
    uri.setDataSource(config.schema, config.table_name, config.geom_column)
    uri.setKeyColumn(config.key_column)
    uri.setWkbType(config.wkb_type)
    uri.setSrid(config.srid)

    layer = _create_qgs_vector_layer(uri, config.layer_name, provider)

    if not layer.isValid():
        raise LayerCreationError(config.layer_name)

    if config.subset_string is not None and not layer.setSubsetString(
        config.subset_string
    ):
        raise LayerCreationError(config.layer_name)

    layer.setReadOnly(config.read_only)
    utils.set_field_aliases(layer, config.aliases)
    utils.set_read_only_fields(layer, [LAYER_ID_COLUMN, *config.read_only_fields])
    utils.set_default_value_expressions(layer, config.default_expressions)

    if config.style_path is not None:
        styles.apply_style(layer, config.style_path)

    layer.setCustomProperty(PINTA_LAYER_ID, config.layer_id)

    if config.value_maps:
        utils.set_value_maps(layer, config)

    return layer
