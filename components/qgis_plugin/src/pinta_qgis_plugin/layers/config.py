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

from pinta_common import env as env_common
from pinta_db.common.base import BaseModel
from pinta_db_utils import model_utils
from qgis.core import QgsWkbTypes
from qgis_plugin_tools.tools import i18n

PINTA_LAYER_ID = "PINTA_LAYER_ID"

COMMON_ALIASES = {
    "id": i18n.tr("Identifier"),
}


@dataclasses.dataclass
class VectorLayerConfig:
    """Configuration for a vector layer."""

    schema: str
    table_name: str
    layer_name: str
    layer_id: str
    key_column: str
    wkb_type: QgsWkbTypes.Type
    srid: str = env_common.SRID
    geom_column: str = "geom"
    aliases: dict[str, str] = dataclasses.field(
        default_factory=lambda: {**COMMON_ALIASES}
    )
    style_path: Path | None = None
    read_only: bool = False


@dataclasses.dataclass
class RasterLayerConfig:
    """Configuration for a raster layer."""

    schema: str
    table_name: str
    layer_name: str
    layer_id: str
    rast_column: str = "rast"
    aliases: dict[str, str] = dataclasses.field(default_factory=dict)
    style_path: Path | None = None


@dataclasses.dataclass
class ModelLayerConfig(VectorLayerConfig):
    """Configuration for a QGIS layer."""

    @staticmethod
    def create(  # noqa: PLR0913
        db_model: type[BaseModel],
        layer_name: str,
        layer_id: str,
        aliases: dict[str, str] | None = None,
        style_path: Path | None = None,
        read_only: bool = False,  # noqa: FBT001, FBT002
    ) -> "ModelLayerConfig":
        """Create a LayerConfig instance."""
        geom_column = model_utils.geometry_column(db_model)
        return ModelLayerConfig(
            schema=_model_schema(db_model),
            table_name=db_model.__tablename__,
            layer_name=layer_name,
            aliases={**COMMON_ALIASES}
            if aliases is None
            else {**COMMON_ALIASES, **aliases},
            geom_column=geom_column,
            key_column=model_utils.primary_key_column(db_model),
            wkb_type=geometry_type_to_qgis_wkb(
                model_utils.geometry_type(db_model, geom_column)
            ),
            style_path=style_path,
            layer_id=layer_id,
            read_only=read_only,
        )


@dataclasses.dataclass
class BasemapLayerConfig:
    """Configuration for a basemap layer."""

    layer_name: str
    uri_parameters: "UriParameters"
    user_name: str | None = None
    password: str | None = None
    aliases: dict[str, str] = dataclasses.field(default_factory=dict)

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


@dataclasses.dataclass
class RasterModelLayerConfig(RasterLayerConfig):
    """Configuration for a PostGIS raster layer."""

    @staticmethod
    def create(
        db_model: type[BaseModel],
        layer_name: str,
        layer_id: str,
        style_path: Path | None = None,
        rast_column: str = "rast",
    ) -> "RasterModelLayerConfig":
        """Create a RasterModelLayerConfig instance."""
        return RasterModelLayerConfig(
            schema=_model_schema(db_model),
            table_name=db_model.__tablename__,
            layer_name=layer_name,
            layer_id=layer_id,
            rast_column=rast_column,
            style_path=style_path,
        )


def geometry_type_to_qgis_wkb(geometry_type: str) -> QgsWkbTypes.Type:
    """Convert a geometry type string to a QgsWkbTypes.Type."""
    mapping = {
        "POLYGON": QgsWkbTypes.Polygon,
        "MULTIPOLYGON": QgsWkbTypes.MultiPolygon,
    }
    return mapping.get(geometry_type.upper())


def _model_schema(db_model: type[BaseModel]) -> str:
    return db_model.__table_args__.get("schema")
