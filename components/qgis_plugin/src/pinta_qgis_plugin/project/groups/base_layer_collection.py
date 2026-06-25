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

from qgis.core import QgsLayerTreeGroup, QgsProject, QgsRasterLayer, QgsVectorLayer

from pinta_qgis_plugin.exceptions import LayerCreationError
from pinta_qgis_plugin.layers.config import BaseLayerConfig

LOGGER = logging.getLogger(__name__)

GROUP_CUSTOM_PROPERTY_ID = "pinta_layer_group_id"


class BaseLayerCollection(abc.ABC):
    """Base class for layer collections."""

    COLLECTION_ID_KEY = "collection_id"
    collection_id: str | None = None

    # Set this to true on subclasses if layers are added
    # to the group instead of the root of the layer tree
    add_layers_to_group: bool = False

    _instance: typing.Optional["BaseLayerCollection"] = None

    @classmethod
    def get(cls) -> "BaseLayerCollection":
        """Get the singleton instance of the class."""
        if cls._instance is None:
            cls._instance = cls()
        return typing.cast("BaseLayerCollection", cls._instance)

    def find_group_from_tree(self) -> QgsLayerTreeGroup | None:
        """Find the group of the collection from the layer tree."""
        all_groups = QgsProject.instance().layerTreeRoot().findGroups(recursive=True)
        return next(
            (
                group
                for group in all_groups
                if group.customProperty(GROUP_CUSTOM_PROPERTY_ID) == self.collection_id
            ),
            None,
        )

    def add_group_to_project(self) -> QgsLayerTreeGroup:
        """Add a group to the project."""
        group = self.find_group_from_tree()
        if group is not None:
            return group

        if self.collection_id is None:
            msg = "Collection ID is not set for the layer collection."
            raise LayerCreationError(msg)

        root = QgsProject.instance().layerTreeRoot()
        group = root.insertGroup(0, self.collection_id)
        group.setCustomProperty(GROUP_CUSTOM_PROPERTY_ID, self.collection_id)
        return group

    def remove_group_from_tree(self) -> None:
        """Remove the group of the collection from the layer tree."""
        if (group := self.find_group_from_tree()) is not None:
            group.removeChildrenGroupWithoutLayers()
            if len(group.children()) == 0:
                parent_group = typing.cast("QgsLayerTreeGroup", group.parent())
                parent_group.removeChildNode(group)
            else:
                group.removeCustomProperty(GROUP_CUSTOM_PROPERTY_ID)

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
        self.remove_group_from_tree()

    def find_layers(self) -> list[QgsVectorLayer | QgsRasterLayer]:
        """Return layers in the collection."""
        return [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if layer.customProperty(self.COLLECTION_ID_KEY) == self.collection_id
        ]

    def _add_map_layer_to_project(
        self,
        layer: QgsVectorLayer | QgsRasterLayer,
        layer_config: BaseLayerConfig,
        group: QgsLayerTreeGroup | None = None,
    ) -> None:
        layer.setCustomProperty(self.COLLECTION_ID_KEY, self.collection_id)
        added_layer = QgsProject.instance().addMapLayer(
            layer, addToLegend=not self.add_layers_to_group
        )
        if added_layer is None:
            raise LayerCreationError(layer.name())
        LOGGER.debug("%s layer loaded successfully", layer.name())

        if group is not None:
            tree_layer = group.addLayer(layer)
        else:
            tree_layer = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if tree_layer is not None:
            tree_layer.setItemVisibilityChecked(layer_config.visible_initially)
