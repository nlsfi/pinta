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

from pinta_db import env
from qgis.core import QgsCoordinateReferenceSystem, QgsProject
from qgis.utils import iface as utils_iface
from qgis_plugin_tools.tools.decorations import log_if_fails

from pinta_qgis_plugin.layers.collections.basemap_layer_collection import (
    BasemapLayerCollection,
)
from pinta_qgis_plugin.layers.collections.management_layer_collection import (
    ManagementLayerCollection,
)

if typing.TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = typing.cast("QgisInterface", utils_iface)

LOGGER = logging.getLogger(__name__)


@log_if_fails
def initialize_project() -> None:
    """Initialize the QGIS project dynamically."""
    BasemapLayerCollection.get().add_to_project()
    ManagementLayerCollection.get().add_to_project()

    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem.fromEpsgId(int(env.SRID)))


@log_if_fails
def clean_project() -> None:
    """Clean QGIS project dynamically."""
    BasemapLayerCollection.get().remove_from_project()
    ManagementLayerCollection.get().remove_from_project()
