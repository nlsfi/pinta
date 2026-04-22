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

"""Layer style utilities."""

import logging
from pathlib import Path

from qgis.core import QgsRasterLayer, QgsVectorLayer

LOGGER = logging.getLogger(__name__)


def apply_style(layer: QgsVectorLayer | QgsRasterLayer, style_path: Path) -> None:
    """Apply a QML style file to a layer."""
    msg, succeeded = layer.loadNamedStyle(str(style_path))
    if not succeeded:
        LOGGER.warning(
            "Could not apply style %s to layer %s: %s",
            style_path,
            layer.name(),
            msg,
        )
    layer.triggerRepaint()
