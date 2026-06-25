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

import typing

from qgis.core import QgsAction, QgsGeometry, QgsVectorLayer
from qgis.utils import iface as utils_iface

if typing.TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = typing.cast("QgisInterface", utils_iface)


def zoom_to_feature(geometry_wkt: str) -> None:
    """Zoom the map canvas to the extent of the given feature geometry.

    The geometry is expected to be in the same CRS as the map canvas.
    """
    geometry = QgsGeometry.fromWkt(geometry_wkt)
    if geometry.isNull() or geometry.isEmpty():
        return

    canvas = iface.mapCanvas()
    canvas.setExtent(geometry.boundingBox())
    canvas.refresh()


def add_action_to_vector_layer(
    layer: QgsVectorLayer,
    *,
    description: str,
    short_title: str,
    command: str,
    scopes: tuple[typing.Literal["Feature", "Layer"], ...] = ("Feature",),
) -> None:
    """Attach a Python action to ``layer`` and show it in the attribute table."""
    action_manager = layer.actions()
    action = QgsAction(
        QgsAction.GenericPython,
        description=description,
        action=command,
        icon=None,
        capture=True,
        shortTitle=short_title,
        actionScopes=list(scopes),
    )

    action.setCommand(command)
    action_manager.addAction(action)

    attribute_table_config = layer.attributeTableConfig()
    attribute_table_config.setActionWidgetVisible(True)
    attribute_table_config.setActionWidgetStyle(
        attribute_table_config.ActionWidgetStyle.ButtonList
    )
    layer.setAttributeTableConfig(attribute_table_config)
