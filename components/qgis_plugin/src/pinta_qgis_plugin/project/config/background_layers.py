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

from pathlib import Path

from pinta_db.primary_db.models.all import Dem
from qgis_plugin_tools.tools import i18n

from pinta_qgis_plugin import env
from pinta_qgis_plugin.layers.config import BasemapLayerConfig, RasterModelLayerConfig

_STYLES_PATH = Path(__file__).parent.parent.parent / "resources" / "styles"

BASEMAP_LAYERS = BasemapLayerConfig.from_json(env.PINTA_BASE_MAP_LAYER_CONFIG)

DEM_LAYER = RasterModelLayerConfig.create(
    db_model=Dem,
    layer_name=i18n.tr("Elevation model"),
    style_path=_STYLES_PATH / "elevation_model.qml",
)

DEM_LAYERS = [
    DEM_LAYER,
]
