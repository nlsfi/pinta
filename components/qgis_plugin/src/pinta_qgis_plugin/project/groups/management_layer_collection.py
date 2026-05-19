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

from qgis.core import QgsAction, QgsVectorLayer
from qgis_plugin_tools.tools import i18n

from pinta_qgis_plugin.config import database
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
            layer = vector_layer.create_vector_layer(
                layer_config, PROVIDER_LIB, database.get_database_uri()
            )
            self._add_map_layer_to_project(layer)
            if layer_config.layer_id == "production_area":
                _add_open_production_area_layers(layer)


def _add_open_production_area_layers(layer: QgsVectorLayer) -> None:
    """Add open production area layer to the project."""
    action_manager = layer.actions()
    action = QgsAction(
        QgsAction.GenericPython,
        description=i18n.tr("Add production area related layers to map"),
        action="",
        icon=None,
        capture=True,
        shortTitle=i18n.tr("Open production area"),
        actionScopes=["Feature"],
    )

    action.setCommand(
        textwrap.dedent("""
        from pinta_qgis_plugin.project.manager import open_production_area
        db_name = \'[%database_name%]\'
        group_name = \'[%name%]\'
        open_production_area(db_name, group_name)
    """)
    )
    action_manager.addAction(action)

    attribute_table_config = layer.attributeTableConfig()
    attribute_table_config.setActionWidgetVisible(True)
    attribute_table_config.setActionWidgetStyle(
        attribute_table_config.ActionWidgetStyle.ButtonList
    )
    layer.setAttributeTableConfig(attribute_table_config)
