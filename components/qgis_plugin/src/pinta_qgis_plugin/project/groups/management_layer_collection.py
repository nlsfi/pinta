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

from pinta_qgis_plugin.layers import vector_layer
from pinta_qgis_plugin.project.config import management_layers
from pinta_qgis_plugin.project.groups.base_layer_collection import (
    BaseLayerCollection,
)

LOGGER = logging.getLogger(__name__)

PROVIDER_LIB = "postgres"


class ManagementLayerCollection(BaseLayerCollection):
    """Collection of management layers."""

    collection_id = "management"

    def _add_to_project(self) -> None:
        """Add layers to the project."""
        for layer_config in reversed(management_layers.VECTOR_LAYERS):
            self._add_map_layer_to_project(
                vector_layer.create_vector_layer(layer_config, PROVIDER_LIB)
            )
