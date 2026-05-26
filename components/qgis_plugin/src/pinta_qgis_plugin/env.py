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
import typing
from pathlib import Path

from qgis_plugin_tools.tools import resources

from pinta_qgis_plugin.exceptions import EnvironmentVariableError

TRUTHY_STRINGS = (
    "1",
    "true",
    "yes",
    "t",
)


def is_truthy(value: str) -> bool:
    """Is string content truthy."""
    return value.lower() in TRUTHY_STRINGS


try:
    PINTA_DB_HOST = os.environ["DB_PRIMARY_HOST"]
    PINTA_DB_PORT = os.environ["DB_PRIMARY_PORT"]
    PINTA_DB_NAME = os.environ["DB_PRIMARY_NAME"]
    PINTA_DB_EDITOR_USER = os.environ["DB_PRIMARY_EDITOR_USER"]
    PINTA_DB_EDITOR_PASSWORD = os.environ["DB_PRIMARY_EDITOR_PASSWORD"]

    PINTA_JOB_DB_HOST = os.environ["DB_JOB_HOST"]
    PINTA_JOB_DB_PORT = os.environ["DB_JOB_PORT"]
    PINTA_JOB_DB_EDITOR_USER = os.environ["DB_JOB_EDITOR_USER"]
    PINTA_JOB_DB_EDITOR_PASSWORD = os.environ["DB_JOB_EDITOR_PASSWORD"]

    PINTA_BACKEND_URL = os.environ["PINTA_BACKEND_URL"]

    PINTA_INITIAL_PROJECT_EXTENT = typing.cast(
        "tuple[float, float, float, float]",
        tuple(map(float, os.environ["PINTA_INITIAL_PROJECT_EXTENT"].split(","))),
    )

    IS_DEVELOPMENT_MODE = is_truthy(os.environ.get("PINTA_DEVELOPMENT_MODE", "0"))

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
    raise EnvironmentVariableError(e.args[0]) from None
