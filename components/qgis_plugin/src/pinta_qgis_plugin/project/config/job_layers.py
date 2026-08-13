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

from pinta_common import Settings
from qgis_plugin_tools.tools.i18n import tr

from pinta_qgis_plugin.layers import config

_STYLES_PATH = pathlib.Path(__file__).parent.parent.parent / "resources" / "styles"

LAYERS: list[config.RasterLayerConfig | config.VectorLayerConfig] = [
    config.RasterLayerConfig(
        schema="reference",
        table_name="dem",
        layer_name=tr("Reference DEM"),
        layer_id="reference_dem",
        style_path=_STYLES_PATH / "elevation_model.qml",
    ),
    config.RasterLayerConfig(
        schema="reference",
        table_name="diff_gt_threshold",
        layer_name=tr("DEM difference"),
        layer_id="dem_diff",
        style_path=_STYLES_PATH / "raster_diff.qml",
    ),
    config.RasterLayerConfig(
        schema="reference",
        table_name="diff_lte_threshold",
        layer_name=tr("DEM difference LTE threshold"),
        layer_id="dem_diff_lte_threshold",
        style_path=_STYLES_PATH / "raster_diff.qml",
        visible_initially=False,
    ),
    config.RasterLayerConfig(
        schema="user_data",
        table_name="dem_preview",
        layer_name=tr("DEM preview"),
        layer_id="dem_preview",
        style_path=_STYLES_PATH / "elevation_model.qml",
        visible_initially=False,
    ),
    config.VectorLayerConfig(
        schema="reference",
        table_name="diff_polygon",
        layer_name=tr("Polygonized DEM difference"),
        layer_id="polygonized_dem_diff",
        geom_column="geom",
        key_column="id",
        wkb_type=config.geometry_type_to_qgis_wkb("POLYGON"),
        srid=Settings.DB_SRID,
        visible_initially=False,
        read_only=True,
        aliases={
            **config.COMMON_ALIASES,
            "energy_sum": tr("Energy sum"),
            "relevance_score": tr("Relevance score"),
        },
    ),
    config.VectorLayerConfig(
        schema="reference",
        table_name="update_area_suggestion",
        layer_name=tr("Modification area suggestions"),
        layer_id="modification_area_suggestions",
        geom_column="geom",
        key_column="id",
        wkb_type=config.geometry_type_to_qgis_wkb("POLYGON"),
        srid=Settings.DB_SRID,
        aliases={
            **config.COMMON_ALIASES,
            "energy_distribution": tr("Cluster significance"),
            "energy_sum": tr("Energy sum"),
            "cluster_area": tr("Cluster area"),
            "elevation": tr("Elevation"),
        },
        read_only_fields=[
            "energy_distribution",
            "energy_sum",
            "cluster_area",
            "elevation",
        ],
        subset_string="energy_distribution >= 1 OR elevation IS NOT NULL",
        style_path=_STYLES_PATH / "update_area_suggestion.qml",
    ),
    config.VectorLayerConfig(
        schema="user_data",
        table_name="update_area",
        layer_name=tr("Update area"),
        layer_id="update_area",
        geom_column="geom",
        key_column="id",
        wkb_type=config.geometry_type_to_qgis_wkb("POLYGON"),
        srid=Settings.DB_SRID,
        style_path=_STYLES_PATH / "update_area.qml",
        aliases={
            **config.COMMON_ALIASES,
            "elevation": tr("Elevation"),
            "dirty": tr("Dirty"),
        },
        read_only_fields=["dirty"],
        # The id primary key has no database-side default, so generate a UUID
        # client-side when a new update area is digitised.
        default_expressions={"id": "uuid('WithoutBraces')"},
    ),
]
