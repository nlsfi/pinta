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

from pinta_common import Settings
from pinta_db.common.base import BaseModel
from pinta_db_utils import model_utils
from qgis.core import QgsWkbTypes
from qgis_plugin_tools.tools.i18n import tr

PINTA_LAYER_ID = "PINTA_LAYER_ID"
LAYER_ID_COLUMN = "id"

COMMON_ALIASES = {
    "id": tr("Identifier"),
}


@dataclasses.dataclass
class ValueMapConfig:
    """Configuration for a value map."""

    field_name: str
    value_map: dict[str, str]


@dataclasses.dataclass(kw_only=True)
class BaseLayerConfig:
    """Base configuration for every layer."""

    layer_name: str
    aliases: dict[str, str] = dataclasses.field(default_factory=dict)
    value_maps: list[ValueMapConfig] | None = None
    visible_initially: bool = True


@dataclasses.dataclass(kw_only=True)
class DatabaseLayerConfig(BaseLayerConfig):
    """Base configuration for database-backed layers."""

    schema: str
    table_name: str
    layer_id: str
    style_path: Path | None = None


@dataclasses.dataclass(kw_only=True)
class VectorLayerConfig(DatabaseLayerConfig):
    """Configuration for a vector layer."""

    key_column: str
    wkb_type: QgsWkbTypes.Type
    srid: str = dataclasses.field(default_factory=lambda: Settings.DB_SRID)
    geom_column: str = "geom"
    aliases: dict[str, str] = dataclasses.field(
        default_factory=lambda: {**COMMON_ALIASES}
    )
    read_only: bool = False
    read_only_fields: list[str] = dataclasses.field(default_factory=list)
    subset_string: str | None = None


@dataclasses.dataclass(kw_only=True)
class RasterLayerConfig(DatabaseLayerConfig):
    """Configuration for a raster layer."""

    rast_column: str = "rast"


@dataclasses.dataclass(kw_only=True)
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
        read_only_fields: list[str] | None = None,
        value_maps: list[ValueMapConfig] | None = None,
        visible_initially: bool = True,  # noqa: FBT001, FBT002
    ) -> "ModelLayerConfig":
        """Create a LayerConfig instance."""
        geom_column = model_utils.geometry_column(db_model)
        schema, table = model_utils.schema_and_table(db_model)
        key_column = model_utils.primary_key_column(db_model)
        return ModelLayerConfig(
            schema=schema,
            table_name=table,
            layer_name=layer_name,
            aliases={**COMMON_ALIASES}
            if aliases is None
            else {**COMMON_ALIASES, **aliases},
            geom_column=geom_column,
            key_column=key_column,
            wkb_type=geometry_type_to_qgis_wkb(
                model_utils.geometry_type(db_model, geom_column)
            ),
            style_path=style_path,
            layer_id=layer_id,
            read_only=read_only,
            read_only_fields=[key_column]
            if read_only_fields is None
            else read_only_fields,
            value_maps=value_maps,
            visible_initially=visible_initially,
        )


@dataclasses.dataclass(kw_only=True)
class BasemapLayerConfig(BaseLayerConfig):
    """Configuration for a basemap layer."""

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


@dataclasses.dataclass(kw_only=True)
class RasterModelLayerConfig(RasterLayerConfig):
    """Configuration for a PostGIS raster layer."""

    @staticmethod
    def create(  # noqa: PLR0913
        db_model: type[BaseModel],
        layer_name: str,
        layer_id: str,
        style_path: Path | None = None,
        rast_column: str = "rast",
        visible_initially: bool = True,  # noqa: FBT001, FBT002
    ) -> "RasterModelLayerConfig":
        """Create a RasterModelLayerConfig instance."""
        schema, table = model_utils.schema_and_table(db_model)
        return RasterModelLayerConfig(
            schema=schema,
            table_name=table,
            layer_name=layer_name,
            layer_id=layer_id,
            rast_column=rast_column,
            style_path=style_path,
            visible_initially=visible_initially,
        )


def geometry_type_to_qgis_wkb(geometry_type: str) -> QgsWkbTypes.Type:
    """Convert a geometry type string to a QgsWkbTypes.Type."""
    mapping = {
        "POLYGON": QgsWkbTypes.Polygon,
        "MULTIPOLYGON": QgsWkbTypes.MultiPolygon,
    }
    return mapping.get(geometry_type.upper())
