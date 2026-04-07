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
import os
from pathlib import Path

from qgis_plugin_tools.tools import resources

from pinta_qgis_plugin.exceptions import MissingEnvironmentError

try:
    PINTA_DB_HOST = os.environ["DB_HOST"]
    PINTA_DB_PORT = os.environ["DB_PORT"]
    PINTA_DB_NAME = os.environ["DB_NAME"]
    PINTA_DB_EDITOR_USER = os.environ["DB_EDITOR_USER"]
    PINTA_DB_EDITOR_PASSWORD = os.environ["DB_EDITOR_PASSWORD"]

    # Configurable layer configs
    if (config_path := os.environ.get("PINTA_BASE_MAP_LAYER_CONFIG")) is None:
        PINTA_BASE_MAP_LAYER_CONFIG = Path(
            resources.resources_path("layer_config", "basemap_layer_config.json")
        )
    else:
        PINTA_BASE_MAP_LAYER_CONFIG = Path(config_path)
        if not PINTA_BASE_MAP_LAYER_CONFIG.exists():
            raise FileNotFoundError(PINTA_BASE_MAP_LAYER_CONFIG)

except KeyError as e:
    raise MissingEnvironmentError(e.args[0]) from None
