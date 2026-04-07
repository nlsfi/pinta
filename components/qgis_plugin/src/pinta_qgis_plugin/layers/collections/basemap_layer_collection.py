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

from pinta_qgis_plugin.layers import config, raster_layer
from pinta_qgis_plugin.layers.collections.base_layer_collection import (
    BaseLayerCollection,
)

LOGGER = logging.getLogger(__name__)

PROVIDER = "wms"


class BasemapLayerCollection(BaseLayerCollection):
    """Collection of base map layers."""

    collection_id = "base_map"

    def _add_to_project(self) -> None:
        for layer_config in reversed(config.BASEMAP_LAYERS):
            self._add_map_layer_to_project(
                raster_layer.create_raster_layer(layer_config, PROVIDER)
            )
