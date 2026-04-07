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
import dataclasses
import json
from pathlib import Path

from pinta_db import env as db_env
from pinta_db.models.all import PointCloudTile, ProductionArea
from pinta_db.models.base import BaseModel
from pinta_db_utils import model_utils
from qgis.core import QgsWkbTypes
from qgis_plugin_tools.tools import i18n

from pinta_qgis_plugin import env


@dataclasses.dataclass
class ModelLayerConfig:
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
    ) -> "ModelLayerConfig":
        """Create a LayerConfig instance."""
        geom_column = model_utils.geometry_column(db_model)
        return ModelLayerConfig(
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


@dataclasses.dataclass
class BasemapLayerConfig:
    """Configuration for a basemap layer."""

    layer_name: str
    uri_parameters: "UriParameters"
    user_name: str | None = None
    password: str | None = None

    @dataclasses.dataclass
    class UriParameters:
        """Parameters for the URI."""

        url: str
        crs: str | None = None
        type: str | None = None
        layers: str | None = None
        format: str = "image/png"
        dpiMode: str = "7"  # noqa: N815
        tilePixelRatio: int = 1  # noqa: N815
        tileMatrixSet: str | None = None  # noqa: N815
        styles: str | None = None
        zmin: int = 0  # noqa: SC200
        zmax: int = 19  # noqa: SC200

    @staticmethod
    def from_json(file_path: Path) -> list["BasemapLayerConfig"]:
        """Read a list of BasemapLayerConfig from a JSON file."""
        with file_path.open("r") as f:
            content = json.load(f)
            return [
                BasemapLayerConfig(
                    uri_parameters=BasemapLayerConfig.UriParameters(
                        **config.pop("uri_parameters", {})
                    ),
                    **config,
                )
                for config in content
            ]

    @property
    def uri_string(self) -> str:
        """Uri string for the layer."""
        uri: str = ""
        if self.user_name is not None:
            uri += f"user='{self.user_name}' "
        if self.password is not None:
            uri += f"password='{self.password}' "
        for key, value in self.uri_parameters.__dict__.items():
            if value is not None:
                uri += f"&{key}={value}"
        return uri[1:]


def _geometry_type_to_qgis_wkb(geometry_type: str) -> QgsWkbTypes.Type:
    mapping = {
        "POLYGON": QgsWkbTypes.Polygon,
        "MULTIPOLYGON": QgsWkbTypes.MultiPolygon,
    }
    return mapping.get(geometry_type.upper())


COMMON_ALIASES = {
    "id": i18n.tr("Identifier"),
}

PRODUCTION_AREA = ModelLayerConfig.create(
    db_model=ProductionArea,
    layer_name=i18n.tr("Production area"),
    aliases={
        **COMMON_ALIASES,
    },
)

POINT_CLOUD_TILE = ModelLayerConfig.create(
    db_model=PointCloudTile,
    layer_name=i18n.tr("Point cloud tile"),
    aliases={
        **COMMON_ALIASES,
    },
)

VECTOR_LAYERS = [
    PRODUCTION_AREA,
    POINT_CLOUD_TILE,
]

BASEMAP_LAYERS = BasemapLayerConfig.from_json(env.PINTA_BASE_MAP_LAYER_CONFIG)
