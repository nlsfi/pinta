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

import abc
import logging
import typing
from typing import Optional

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from pinta_qgis_plugin.exceptions import LayerCreationError

LOGGER = logging.getLogger(__name__)


class BaseLayerCollection(abc.ABC):
    """Base class for layer collections."""

    COLLECTION_ID_KEY = "collection_id"

    collection_id: str
    _instance: Optional["BaseLayerCollection"] = None

    @classmethod
    def get(cls) -> "BaseLayerCollection":
        """Get the singleton instance of the class."""
        if cls._instance is None:
            cls._instance = cls()
        return typing.cast("BaseLayerCollection", cls._instance)

    def add_to_project(self) -> None:
        """Add layers to the project."""
        if self.find_layers():
            self.remove_from_project()
        self._add_to_project()

    @abc.abstractmethod
    def _add_to_project(self) -> None:
        """Add layers and groups to the project."""

    def remove_from_project(self) -> None:
        """Remove layers from the project."""
        for layer in self.find_layers():
            QgsProject.instance().removeMapLayer(layer)

    def find_layers(self) -> list[QgsVectorLayer | QgsRasterLayer]:
        """Return layers in the collection."""
        return [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if layer.customProperty(self.COLLECTION_ID_KEY) == self.collection_id
        ]

    def _add_map_layer_to_project(self, layer: QgsVectorLayer | QgsRasterLayer) -> None:
        layer.setCustomProperty(self.COLLECTION_ID_KEY, self.collection_id)

        added_layer = QgsProject.instance().addMapLayer(layer, addToLegend=True)
        if added_layer is not None:
            LOGGER.debug("%s layer loaded successfully", layer.name())
        else:
            raise LayerCreationError(layer.name())
