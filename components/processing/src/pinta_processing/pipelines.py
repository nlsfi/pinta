# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import functools
import logging
import operator
from pathlib import Path

import numpy as np
from pinta_common import Settings
from pinta_db.job_db.models import reference, user
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from pinta_db_utils.postgis import raster
from shapely import wkt as shapely_wkt
from sqlmodel import Session

from pinta_processing import core, filters, reader, writer
from pinta_processing.filters.interpolate import SAMPLING_MARGIN
from pinta_processing.scripts import find_intersecting_tiles
from pinta_processing.utils import tm35_map_sheet_utils

DEFAULT_BUFFERED = 300
DISSOLVE_INTERPOLATE_AREA_BUFFER = 4  # Interpolate zone around the update area
# Extra margin in meters on top of what the seam interpolation strictly needs
# when reading the primary DEM around the update area.
DISSOLVE_PRIMARY_DEM_MARGIN = 10
# Read the primary DEM buffered by this
DISSOLVE_PRIMARY_DEM_BUFFER = (
    DISSOLVE_INTERPOLATE_AREA_BUFFER
    + SAMPLING_MARGIN * Settings.DB_DEM_PIXEL_SIZE
    + DISSOLVE_PRIMARY_DEM_MARGIN
)
# The dissolve rewrites dem_preview inside the update area, in the interpolated
# seam donut around it, and in edge pixels the reference DEM clip only touches.
# Buffer the register read by the interpolate zone plus one pixel so every
# pixel the dissolve may have changed is copied back to the primary DEM.
REGISTER_UPDATE_AREA_BUFFER = (
    DISSOLVE_INTERPOLATE_AREA_BUFFER + Settings.DB_DEM_PIXEL_SIZE
)
DEFAULT_LASTOOLS_PARAMS = {
    "buffered": DEFAULT_BUFFERED,
    "kill": 300,
    "ncols": 500,
    "nrows": 500,
}

LOGGER = logging.getLogger(__name__)


def rasterio_to_geotiff(
    input_path: str, output_path: str, crs: str | None = f"EPSG:{Settings.DB_SRID}"
) -> core.Pipeline:
    """Read rasterio input and write it as geotiff."""
    return reader.RasterioReader(input_path, crs=crs) | writer.GeotiffWriter(
        output_path
    )


def rasterio_to_postgis(  # noqa: PLR0913
    session: Session,
    input_path: Path,
    schema: str,
    table_name: str,
    staging_tables: int = 1,
    crs: str | None = f"EPSG:{Settings.DB_SRID}",
) -> core.Pipeline:
    """Read rasterio input and write it to PostGIS with overviews."""
    return (
        reader.RasterioReader(input_path, crs=crs)
        # Calculate and write overviews
        | _generate_overview_stages(schema, table_name, session, staging_tables)
        # Write original data
        | writer.RasterPostgisWriter(schema, table_name, session, staging_tables)
    )


def blast2dem_to_postgis(  # noqa: PLR0913
    primary_session: Session,
    job_session: Session,
    input_path: Path,
    step: int,
    keep_class: list[int],
    staging_tables: int = 1,
    crs: str = f"EPSG:{Settings.DB_SRID}",
    extra_lastools_params: dict | None = None,
) -> core.Pipeline:
    """Read LAS/LAZ with blast2dem and write to PostGIS with overviews."""
    bounds = tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(input_path.stem)
    neighbor_paths = find_intersecting_tiles.find_neighboring_tm35_laz_files(
        input_path, DEFAULT_BUFFERED, primary_session
    )
    LOGGER.debug("Found %d neighbor tiles", len(neighbor_paths))
    neighbors_param = {}
    if len(neighbor_paths) > 0:
        neighbors_param = {"neighbors": [str(neighbor) for neighbor in neighbor_paths]}
    bounds_param = {"ll": [bounds[0], bounds[1]]}
    extra_lastools_params = {
        **DEFAULT_LASTOOLS_PARAMS,
        **neighbors_param,
        **bounds_param,
        **(extra_lastools_params or {}),
    }

    schema, table_name = model_utils.schema_and_table(reference.Dem)
    return (
        reader.Blast2DemReader(
            input_path,
            step=step,
            crs=crs,
            keep_class=keep_class,
            extra_lastools_params=extra_lastools_params,
        )
        # Calculate and write overviews
        | _generate_overview_stages(schema, table_name, job_session, staging_tables)
        # Write original data
        | writer.RasterPostgisWriter(schema, table_name, job_session, staging_tables)
    )


def calculate_diff_models(
    primary_session: Session,
    job_session: Session,
    tile_wkt: str,
    staging_tables: int = 1,
    threshold: float = 0.2,
) -> core.Pipeline:
    """Calculate difference models between DEM and reference DEM.

    If difference > threshold, values fall in DiffGtThreshold and DiffPolygon tables.
    Otherwise values fall in DiffLteThreshold table.
    """
    dem_schema, dem_table = model_utils.schema_and_table(dem.Dem)
    reference_schema, reference_dem_table = model_utils.schema_and_table(reference.Dem)
    diff_schema, diff_table = model_utils.schema_and_table(reference.DiffGtThreshold)
    lte_threshold_schema, lte_threshold_table = model_utils.schema_and_table(
        reference.DiffLteThreshold
    )
    diff_polygon_schema, diff_polygon_table = model_utils.schema_and_table(
        reference.DiffPolygon
    )

    return (
        reader.PostgisReader(
            dem_schema,
            dem_table,
            primary_session,
            tile_wkt,
        )
        | core.Zip(
            reader.PostgisReader(
                reference_schema,
                reference_dem_table,
                job_session,
                tile_wkt,
            )
        )
        | filters.RasterDiff()
        # Diff
        | core.Tee(
            filters.RasterFilter(lambda x: np.abs(x) > threshold)
            # Calculate and write overviews
            | _generate_overview_stages(
                diff_schema, diff_table, job_session, staging_tables
            )
            # Write raster
            | core.Tee(
                writer.RasterPostgisWriter(
                    diff_schema, diff_table, job_session, staging_tables
                )
            )
            # Write vector
            | filters.VectorizeRaster()
            | writer.VectorPostgisWriter(
                diff_polygon_schema, diff_polygon_table, job_session
            )
        )
        # Diff lte threshold
        | core.Tee(
            filters.RasterFilter(lambda x: np.abs(x) <= threshold)
            # Calculate and write overviews
            | _generate_overview_stages(
                lte_threshold_schema, lte_threshold_table, job_session, staging_tables
            )
            # Write raster
            | writer.RasterPostgisWriter(
                lte_threshold_schema, lte_threshold_table, job_session, staging_tables
            )
        )
    )


def dissolve_update_area(
    primary_session: Session,
    job_session: Session,
    update_area: user.UpdateArea,
) -> core.Pipeline:
    """Merge the primary and reference DEM and smooth the update area seam.

    - Read primary DEM as a DISSOLVE_PRIMARY_DEM_BUFFER wide ring around the update
      area, the interior is clipped out since the reference DEM wins there anyway.
    - Read reference DEM clipped to the update area. When the update area has a
      constant elevation set, the reference DEM is not read at all: a flat raster
      at that elevation is built from scratch with RasterMask instead.
    - Union the DEMs, reference dem has priority.
    - Interpolate DISSOLVE_INTERPOLATE_AREA_BUFFER meters wide donut outside the update
      area to smooth the seam.

    The blended result is merged into dem_preview and its overviews. Overviews are
    downsampled from the blended patch, so under concurrent update-area tasks a shared
    overview tile may end up with slightly stale value (overview are visualization-only)
    Only dem_preview needs to be eventually consistent, which the
    tile-level merge guarantees.
    """
    geom = shapely_wkt.loads(update_area.geom_wkt)
    primary_dem_area = geom.buffer(DISSOLVE_PRIMARY_DEM_BUFFER).difference(geom)
    buffer_zone_area = geom.buffer(DISSOLVE_INTERPOLATE_AREA_BUFFER).difference(geom)

    dem_schema, dem_table = model_utils.schema_and_table(dem.Dem)
    preview_schema, preview_table = model_utils.schema_and_table(user.DemPreview)

    if update_area.elevation is not None:
        update_area_reader_or_mask: core.Stage = filters.RasterMask(
            geom.wkt, update_area.elevation
        )
    else:
        reference_schema, reference_dem_table = model_utils.schema_and_table(
            reference.Dem
        )
        update_area_reader_or_mask = reader.PostgisReader(
            reference_schema,
            reference_dem_table,
            job_session,
            geom.wkt,
        )

    return (
        reader.PostgisReader(
            dem_schema, dem_table, primary_session, primary_dem_area.wkt
        )
        | core.Zip(update_area_reader_or_mask)
        | filters.RasterUnion()
        | filters.RasterInterpolate(buffer_zone_area.wkt)
        | _generate_overview_stages(
            preview_schema, preview_table, job_session, staging_tables=0, mode="update"
        )
        | writer.RasterPostgisWriter(
            preview_schema, preview_table, job_session, mode="update"
        )
    )


def postgis_to_postgis(  # noqa: PLR0913
    from_session: Session,
    from_schema: str,
    from_table: str,
    to_session: Session,
    to_schema: str,
    to_table: str,
    tile_wkt: str,
    staging_tables: int = 0,
    mode: writer.WriterMode = "insert",
) -> core.Pipeline:
    """Read raster from Postgis, write to Postgis."""
    return (
        reader.PostgisReader(
            from_schema,
            from_table,
            from_session,
            tile_wkt,
        )
        | _generate_overview_stages(
            to_schema, to_table, to_session, staging_tables, mode
        )
        | writer.RasterPostgisWriter(
            to_schema, to_table, to_session, staging_tables, mode=mode
        )
    )


def _generate_overview_stages(
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
    mode: writer.WriterMode = "insert",
) -> core.Stage:
    return functools.reduce(
        operator.or_,
        [
            core.Tee(
                _overview_to_postgis(
                    level,
                    schema,
                    raster.OVERVIEW_TABLE_NAME.format(
                        level=level, table_name=table_name
                    ),
                    session,
                    staging_tables,
                    mode,
                )
            )
            for level in raster.DEFAULT_OVERVIEW_LEVELS
        ],
    )


def _overview_to_postgis(  # noqa: PLR0913
    factor: int,
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
    mode: writer.WriterMode = "insert",
) -> core.Pipeline:
    return filters.DownsampleOverview(factor) | writer.RasterPostgisWriter(
        schema, table_name, session, staging_tables, mode=mode
    )
