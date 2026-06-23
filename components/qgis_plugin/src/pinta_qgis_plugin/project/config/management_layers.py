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
from qgis_plugin_tools.tools.i18n import tr

from pinta_qgis_plugin.layers import config
from pinta_qgis_plugin.layers.config import ModelLayerConfig

PRODUCTION_AREA = ModelLayerConfig.create(
    db_model=ProductionArea,
    layer_name=tr("Production area"),
    layer_id="production_area",
    read_only=True,
    aliases={
        **config.COMMON_ALIASES,
        "name": tr("Name"),
        "database_name": tr("Database name"),
        "processing_status": tr("Processing status"),
    },
    value_maps=[
        config.ValueMapConfig(
            field_name="processing_status",
            value_map={
                "not_started": tr("Pending"),
                "queued": tr("Queued"),
                "started": tr("Started"),
                "completed": tr("Completed"),
                "failed": tr("Failed"),
            },
        )
    ],
)

POINT_CLOUD_TILE = ModelLayerConfig.create(
    db_model=PointCloudTile,
    layer_name=tr("Point cloud tile"),
    layer_id="point_cloud_tile",
    read_only=True,
    aliases={
        **config.COMMON_ALIASES,
        "file_path": tr("File path"),
        "production_area_id": tr("Production area ID"),
    },
)

VECTOR_LAYERS = [
    PRODUCTION_AREA,
    POINT_CLOUD_TILE,
]
