# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path

from pinta_common import env
from sqlmodel import Session

from pinta_processing import core, filters, reader, writer


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
        | core.Tee(
            _overview_to_postgis(
                2, schema, f"o_2_{table_name}", session, staging_tables
            )
        )
        | core.Tee(
            _overview_to_postgis(
                8, schema, f"o_8_{table_name}", session, staging_tables
            )
        )
        | core.Tee(
            _overview_to_postgis(
                128, schema, f"o_128_{table_name}", session, staging_tables
            )
        )
        # Write original data
        | writer.PostgisWriter(schema, table_name, session, staging_tables)
    )


def _overview_to_postgis(
    factor: int,
    schema: str,
    table_name: str,
    session: Session,
    staging_tables: int,
) -> core.Pipeline:
    return filters.DownsampleOverview(factor) | writer.PostgisWriter(
        schema, table_name, session, staging_tables
    )
