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
import typing

from qgis.core import QgsLayerTreeGroup, QgsProject

from pinta_qgis_plugin import exceptions
from pinta_qgis_plugin.config import database
from pinta_qgis_plugin.layers import config, raster_layer, vector_layer
from pinta_qgis_plugin.project.config import job_layers
from pinta_qgis_plugin.project.groups.base_layer_collection import (
    GROUP_CUSTOM_PROPERTY_ID,
    BaseLayerCollection,
)

LOGGER = logging.getLogger(__name__)


JOB_COLLECTION_ID = "job_{database_name}"
JOB_COLLECTION_ID_PREFIX = "job_"
VECTOR_PROVIDER = "postgres"
RASTER_PROVIDER = "postgresraster"


class JobLayerCollection(BaseLayerCollection):
    """Collection of production area related layers."""

    database_name: str | None = None
    group_name: str | None = None
    add_layers_to_group = True

    def __init__(self) -> None:
        super().__init__()

    def add_to_project(self) -> None:
        """Add layers to the project."""
        if self.find_layers():
            self.remove_from_project()
        self._add_to_project()

    def set_database_name(self, database_name: str) -> None:
        """Set the database name for the job layers."""
        self.database_name = database_name
        self.collection_id = JOB_COLLECTION_ID.format(database_name=database_name)

    def set_group_name(self, group_name: str) -> None:
        """Set the group name for the job layers."""
        self.group_name = group_name

    @classmethod
    def remove_all_from_project(cls) -> None:
        """Remove all job layer collections from the project."""
        project = QgsProject.instance()
        groups = [
            group
            for group in project.layerTreeRoot().findGroups(recursive=True)
            if str(group.customProperty(GROUP_CUSTOM_PROPERTY_ID)).startswith(
                JOB_COLLECTION_ID_PREFIX
            )
        ]
        collection_ids = {
            group.customProperty(GROUP_CUSTOM_PROPERTY_ID) for group in groups
        }

        for layer in list(project.mapLayers().values()):
            if layer.customProperty(cls.COLLECTION_ID_KEY) in collection_ids:
                project.removeMapLayer(layer)

        for group in groups:
            parent_group = typing.cast("QgsLayerTreeGroup | None", group.parent())
            if parent_group is not None:
                parent_group.removeChildNode(group)

    def _add_to_project(self) -> None:
        """Add layers to the project."""
        if self.database_name is None:
            msg = "Database name is required to add job layers."
            raise exceptions.LayerCreationError(msg)

        group = self.add_group_to_project()

        if self.group_name is None:
            msg = "Group name is required to add job layers."
            raise exceptions.LayerCreationError(msg)
        group.setName(self.group_name)

        for layer_config in reversed(job_layers.LAYERS):
            try:
                uri = database.get_job_database_uri(self.database_name)
                layer = None
                if isinstance(layer_config, config.VectorLayerConfig):
                    layer = vector_layer.create_vector_layer(
                        layer_config,
                        VECTOR_PROVIDER,
                        uri,
                    )
                if isinstance(layer_config, config.RasterLayerConfig):
                    layer = raster_layer.create_postgis_raster_layer(
                        layer_config,
                        RASTER_PROVIDER,
                        uri,
                    )
                self._add_map_layer_to_project(layer)
                group.addLayer(layer)
            except exceptions.LayerCreationError:
                LOGGER.exception("Failed to create layer %s", layer_config.layer_name)
