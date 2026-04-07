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

from qgis_plugin_tools.tools.decorations import log_if_fails

from pinta_qgis_plugin.layers import vector_layer

LOGGER = logging.getLogger(__name__)


@log_if_fails
def initialize_layers() -> None:
    """Initialize and load all layers into QGIS project."""
    vector_layer.add_vector_layers()


@log_if_fails
def remove_layers() -> None:
    """Remove all layers from QGIS project."""
    vector_layer.remove_vector_layers()
