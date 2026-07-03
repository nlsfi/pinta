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
import textwrap

from qgis.core import QgsVectorLayer
from qgis_plugin_tools.tools.i18n import tr

from pinta_qgis_plugin.config import database
from pinta_qgis_plugin.layers import vector_layer
from pinta_qgis_plugin.project.config import management_layers
from pinta_qgis_plugin.project.groups.base_layer_collection import (
    BaseLayerCollection,
)
from pinta_qgis_plugin.utils import layer_utils

LOGGER = logging.getLogger(__name__)

PROVIDER_LIB = "postgres"

ACTION_TITLE_OPEN_PRODUCTION_AREA_LAYERS = tr("Open production area")
ACTION_TITLE_START_REFERENCE_DEM_WORKFLOW = tr("Start reference DEM workflow")
ACTION_TITLE_START_DISSOLVE_UPDATE_AREAS = tr("Dissolve update areas")


class ManagementLayerCollection(BaseLayerCollection):
    """Collection of management layers."""

    collection_id = "management"

    def _add_to_project(self) -> None:
        """Add layers to the project."""
        for layer_config in reversed(management_layers.VECTOR_LAYERS):
            layer = vector_layer.create_vector_layer(
                layer_config, PROVIDER_LIB, database.get_database_uri()
            )
            self._add_map_layer_to_project(layer, layer_config)
            if layer_config.layer_id == "production_area":
                _add_open_production_area_layers_action(layer)
                _add_start_reference_dem_workflow_action(layer)
                _add_start_dissolve_update_areas_action(layer)


def _add_open_production_area_layers_action(layer: QgsVectorLayer) -> None:
    """Add open production area layer action to the the layer."""
    command = textwrap.dedent("""
        from pinta_qgis_plugin.project.manager import open_production_area
        from pinta_qgis_plugin.utils.layer_utils import zoom_to_feature
        db_name = \'[%database_name%]\'
        group_name = \'[%name%]\'
        if open_production_area(db_name, group_name):
            zoom_to_feature(\'[%geom_to_wkt($geometry)%]\')
    """)
    layer_utils.add_action_to_vector_layer(
        layer,
        description=tr("Add production area related layers to map"),
        short_title=ACTION_TITLE_OPEN_PRODUCTION_AREA_LAYERS,
        command=command,
    )


def _add_start_reference_dem_workflow_action(layer: QgsVectorLayer) -> None:
    """Add start reference dem workflow action to the layer."""
    command = textwrap.dedent("""
        from pinta_qgis_plugin.workflows import dem
        job_id = \'[%id%]\'
        dem.start_reference_dem_workflow(job_id)
    """)
    layer_utils.add_action_to_vector_layer(
        layer,
        description=tr("Start reference DEM workflow for production area"),
        short_title=ACTION_TITLE_START_REFERENCE_DEM_WORKFLOW,
        command=command,
    )


def _add_start_dissolve_update_areas_action(layer: QgsVectorLayer) -> None:
    """Add start dissolve update areas action to the layer."""
    command = textwrap.dedent("""
        from pinta_qgis_plugin.workflows import update_area
        job_id = \'[%id%]\'
        update_area.start_dissolve_update_areas_workflow(job_id)
    """)
    layer_utils.add_action_to_vector_layer(
        layer,
        description=tr("Start dissolve update areas workflow for production area"),
        short_title=ACTION_TITLE_START_DISSOLVE_UPDATE_AREAS,
        command=command,
    )
