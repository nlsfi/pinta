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

from pinta_db.primary_db.models.all import PointCloudTile, ProductionArea
from qgis_plugin_tools.tools import i18n

from pinta_qgis_plugin.layers.config import ModelLayerConfig

PRODUCTION_AREA = ModelLayerConfig.create(
    db_model=ProductionArea,
    layer_name=i18n.tr("Production area"),
    layer_id="production_area",
    read_only=True,
)

POINT_CLOUD_TILE = ModelLayerConfig.create(
    db_model=PointCloudTile,
    layer_name=i18n.tr("Point cloud tile"),
    layer_id="point_cloud_tile",
    read_only=True,
)

VECTOR_LAYERS = [
    PRODUCTION_AREA,
    POINT_CLOUD_TILE,
]
