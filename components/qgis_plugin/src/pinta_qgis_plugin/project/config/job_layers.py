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

import pathlib

from pinta_common import env
from qgis_plugin_tools.tools import i18n

from pinta_qgis_plugin.layers import config

_STYLES_PATH = pathlib.Path(__file__).parent.parent.parent / "resources" / "styles"

LAYERS: list[config.RasterLayerConfig | config.VectorLayerConfig] = [
    config.RasterLayerConfig(
        schema="reference",
        table_name="dem",
        layer_name=i18n.tr("Reference DEM"),
        layer_id="reference_dem",
        style_path=_STYLES_PATH / "elevation_model.qml",
    ),
    config.RasterLayerConfig(
        schema="reference",
        table_name="diff",
        layer_name=i18n.tr("DEM difference"),
        layer_id="dem_diff",
    ),
    config.RasterLayerConfig(
        schema="reference",
        table_name="diff_dior",
        layer_name=i18n.tr("DEM difference DIOR"),
        layer_id="dem_diff_dior",
    ),
    config.VectorLayerConfig(
        schema="reference",
        table_name="diff_polygon",
        layer_name=i18n.tr("Polygonized DEM difference"),
        layer_id="polygonized_dem_diff",
        geom_column="geom",
        key_column="id",
        wkb_type=config.geometry_type_to_qgis_wkb("POLYGON"),
        srid=env.SRID,
    ),
    config.VectorLayerConfig(
        schema="reference",
        table_name="diff_polygon_cluster",
        layer_name=i18n.tr("Modification area suggestions"),
        layer_id="modification_area_suggestions",
        geom_column="geom",
        key_column="id",
        wkb_type=config.geometry_type_to_qgis_wkb("POLYGON"),
        srid=env.SRID,
        aliases={
            **config.COMMON_ALIASES,
            "energy_distribution": i18n.tr("Cluster significance"),
        },
    ),
]
