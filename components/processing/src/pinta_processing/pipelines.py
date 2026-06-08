# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path

from pinta_common import env
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
    return core.Pipeline(
        [
            reader.RasterioReader(input_path, crs=crs),
            # Calculate and write overviews
            *_generate_overview_stages(schema, table_name, session, staging_tables),
            # Write original data
            writer.RasterPostgisWriter(schema, table_name, session, staging_tables),
        ]
    )


def _generate_overview_stages(
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
) -> list[core.Stage]:
    return [
        core.Tee(
            _overview_to_postgis(
                level,
                schema,
                raster.OVERVIEW_TABLE_NAME.format(level=level, table_name=table_name),
                session,
                staging_tables,
            )
        )
        for level in raster.DEFAULT_OVERVIEW_LEVELS
    ]


def blast2dem_to_geotiff(  # noqa: PLR0913
    input_path: Path,
    output_path: str,
    step: int,
    keep_class: list[int],
    crs: str = f"EPSG:{env.SRID}",
    extra_lastools_params: dict | None = None,
) -> core.Pipeline:
    """Read LAS/LAZ with blast2dem and write as GeoTIFF."""
    return reader.Blast2DemReader(
        input_path,
        step=step,
        crs=crs,
        keep_class=keep_class,
        extra_lastools_params=extra_lastools_params,
    ) | writer.GeotiffWriter(output_path)


def blast2dem_to_postgis(  # noqa: PLR0913
    session: Session,
    input_path: Path,
    schema: str,
    table_name: str,
    step: int,
    keep_class: list[int],
    staging_tables: int = 1,
    crs: str = f"EPSG:{env.SRID}",
    extra_lastools_params: dict | None = None,
) -> core.Pipeline:
    """Read LAS/LAZ with blast2dem and write to PostGIS with overviews."""
    bounds = tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(input_path.stem)
    neighbor_paths = find_intersecting_tiles.find_neighboring_tm35_laz_files(
        input_path, DEFAULT_BUFFERED, session
    )
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

    return core.Pipeline(
        [
            reader.Blast2DemReader(
                input_path,
                step=step,
                crs=crs,
                keep_class=keep_class,
                extra_lastools_params=extra_lastools_params,
            ),
            # Calculate and write overviews
            *_generate_overview_stages(schema, table_name, session, staging_tables),
            # Write original data
            writer.RasterPostgisWriter(schema, table_name, session, staging_tables),
        ]
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
