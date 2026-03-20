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
from dataclasses import dataclass

from pinta_db import env as db_env
from pinta_db.models.all import PointCloudTile, ProductionArea
from pinta_db.models.base import BaseModel
from pinta_db_utils import model_utils
from qgis.core import QgsWkbTypes
from qgis_plugin_tools.tools import i18n


@dataclass
class LayerConfig:
    """Configuration for a QGIS layer."""

    db_model: type[BaseModel]
    layer_name: str
    aliases: dict[str, str]
    geom_column: str
    key_column: str
    wkb_type: QgsWkbTypes.Type
    srid: str

    @staticmethod
    def create(
        db_model: type[BaseModel],
        layer_name: str,
        aliases: dict[str, str],
    ) -> "LayerConfig":
        """Create a LayerConfig instance."""
        geom_column = model_utils.geometry_column(db_model)
        return LayerConfig(
            db_model=db_model,
            layer_name=layer_name,
            aliases=aliases,
            geom_column=geom_column,
            key_column=model_utils.primary_key_column(db_model),
            wkb_type=_geometry_type_to_qgis_wkb(
                model_utils.geometry_type(db_model, geom_column)
            ),
            srid=db_env.SRID,
        )


def _geometry_type_to_qgis_wkb(geometry_type: str) -> QgsWkbTypes.Type:
    mapping = {
        "POLYGON": QgsWkbTypes.Polygon,
        "MULTIPOLYGON": QgsWkbTypes.MultiPolygon,
    }
    return mapping.get(geometry_type.upper())


COMMON_ALIASES = {
    "id": i18n.tr("Identifier"),
}

PRODUCTION_AREA = LayerConfig.create(
    db_model=ProductionArea,
    layer_name=i18n.tr("Production area"),
    aliases={
        **COMMON_ALIASES,
    },
)

POINT_CLOUD_TILE = LayerConfig.create(
    db_model=PointCloudTile,
    layer_name=i18n.tr("Point cloud tile"),
    aliases={
        **COMMON_ALIASES,
    },
)

LAYERS = [
    PRODUCTION_AREA,
    POINT_CLOUD_TILE,
]
