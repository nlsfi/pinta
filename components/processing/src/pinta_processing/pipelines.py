# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import functools
import logging
import operator
from pathlib import Path

import numpy as np
from pinta_common import env
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from pinta_db_utils.postgis import raster
from sqlmodel import Session

from pinta_processing import core, filters, reader, writer
from pinta_processing.scripts import find_intersecting_tiles
from pinta_processing.utils import tm35_map_sheet_utils

DEFAULT_BUFFERED = 300
DEFAULT_LASTOOLS_PARAMS = {
    "buffered": DEFAULT_BUFFERED,
    "kill": 300,
    "ncols": 500,
    "nrows": 500,
}

LOGGER = logging.getLogger(__name__)


def rasterio_to_geotiff(
    input_path: str, output_path: str, crs: str = f"EPSG:{env.SRID}"
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
    crs: str | None = f"EPSG:{env.SRID}",
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
    crs: str = f"EPSG:{env.SRID}",
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


def _generate_overview_stages(
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
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
                )
            )
            for level in raster.DEFAULT_OVERVIEW_LEVELS
        ],
    )


def _overview_to_postgis(
    factor: int,
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
) -> core.Pipeline:
    return filters.DownsampleOverview(factor) | writer.RasterPostgisWriter(
        schema, table_name, session, staging_tables
    )
