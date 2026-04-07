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

from qgis.core import QgsDataSourceUri, QgsProject, QgsVectorLayer

from pinta_qgis_plugin.exceptions import LayerCreationError
from pinta_qgis_plugin.layers import config, database
from pinta_qgis_plugin.layers.config import ModelLayerConfig

LOGGER = logging.getLogger(__name__)

PROVIDER_LIB = "postgres"


def _create_qgs_vector_layer(uri: QgsDataSourceUri, name: str) -> QgsVectorLayer:
    return QgsVectorLayer(uri.uri(), name, PROVIDER_LIB)


def create_vector_layer(config: ModelLayerConfig) -> QgsVectorLayer:
    """Create Production areas layer from database."""
    uri = database.get_database_uri()

    schema = config.db_model.__table_args__.get("schema")
    table_name = config.db_model.__tablename__
    uri.setDataSource(schema, table_name, config.geom_column)
    uri.setKeyColumn(config.key_column)
    uri.setWkbType(config.wkb_type)
    uri.setSrid(config.srid)

    layer = _create_qgs_vector_layer(uri, config.layer_name)

    if not layer.isValid():
        raise LayerCreationError(config.layer_name)

    layer.setReadOnly(True)

    return layer


def add_vector_layers() -> None:
    """Add vector layers into the QGIS project."""
    for layer_config in config.VECTOR_LAYERS:
        layer_name = layer_config.layer_name
        layer = create_vector_layer(layer_config)

        added_layer = QgsProject.instance().addMapLayer(layer, addToLegend=True)
        if added_layer is not None:
            LOGGER.info("%s layer loaded successfully", layer_name)
        else:
            raise LayerCreationError(layer_name)


def remove_vector_layers() -> None:
    """Remove vector layers from the QGIS project."""
    all_vector_layers = {
        layer.name(): layer
        for layer in QgsProject.instance().mapLayers().values()
        if isinstance(layer, QgsVectorLayer)
    }
    for layer_config in config.VECTOR_LAYERS:
        if layer_config.layer_name in all_vector_layers:
            QgsProject.instance().removeMapLayer(
                all_vector_layers[layer_config.layer_name].id()
            )
