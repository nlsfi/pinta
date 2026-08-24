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

from pinta_common import Settings
from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsRectangle
from qgis.utils import iface as utils_iface
from qgis_plugin_tools.tools.decorations import log_if_fails
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from pinta_qgis_plugin import env as plugin_env
from pinta_qgis_plugin.project.groups.basemap_layer_collection import (
    BasemapLayerCollection,
)
from pinta_qgis_plugin.project.groups.dem_layer_collection import DemLayerCollection
from pinta_qgis_plugin.project.groups.job_layer_collection import JobLayerCollection
from pinta_qgis_plugin.project.groups.management_layer_collection import (
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
    DemLayerCollection.get().add_to_project()
    ManagementLayerCollection.get().add_to_project()

    # TODO: By default QgsProject.instance().setCrs() has no effect here and the project
    # will have crs of first added layer in BasemapLayerCollection. By default
    # QGIS will set project crs to match the first added layer. We can not change the
    # global setting "projections\defaultProjectCrs" as it will affect every project
    # created by the QGIS installation.
    QgsProject.instance().setCrs(
        QgsCoordinateReferenceSystem.fromEpsgId(int(Settings.DB_SRID))
    )
    iface.mapCanvas().setExtent(QgsRectangle(*plugin_env.PINTA_INITIAL_PROJECT_EXTENT))


@log_if_fails
def clean_project() -> None:
    """Clean QGIS project dynamically."""
    BasemapLayerCollection.get().remove_from_project()
    DemLayerCollection.get().remove_from_project()
    ManagementLayerCollection.get().remove_from_project()
    JobLayerCollection.remove_all_from_project()


def open_production_area(database_name: str | None, group_name: str) -> bool:
    """Open production area layer. Return True if the layers were opened."""
    if not database_name:
        MsgBar.info(tr("Production area does not have database name set."))
        return False
    collection = typing.cast("JobLayerCollection", JobLayerCollection.get())
    collection.set_database_name(database_name)
    collection.set_group_name(group_name)
    collection.add_to_project()
    return True


def close_production_area(database_name: str) -> None:
    """Remove the layers of the production area's job database from the project."""
    collection = typing.cast("JobLayerCollection", JobLayerCollection.get())
    collection.set_database_name(database_name)
    collection.remove_from_project()
