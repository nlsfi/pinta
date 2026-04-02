# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import tempfile
import typing
from pathlib import Path

import numpy as np
import rasterio
import sqlalchemy as sa
from pinta_db_utils.postgis import raster
from pinta_test_utils import pinta_utils

from pinta_processing import reader, writer

if typing.TYPE_CHECKING:
    from sqlmodel import Session


def test_postgis_writer(processing_worker_session: "Session") -> None:
    raster.initialize_raster_table(processing_worker_session, "dem", "processing")
    file_path = pinta_utils.get_test_data_path("processing/dem.tif")

    # Read input raster
    with rasterio.open(str(file_path)) as src:
        input_array = src.read(1)
        input_crs = src.crs

    # Execute pipeline to tile and write to PostGIS
    pipeline = reader.RasterioReader(str(file_path)) | writer.PostgisWriter(
        "processing", "dem", processing_worker_session
    )
    pipeline.execute()

    # Verify 4 tiles were written to database
    tile_count_result = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text("SELECT COUNT(*) FROM processing.dem")
    ).first()
    assert tile_count_result == (4,), f"Expected 4 tiles, got {tile_count_result[0]}"

    # Query PostGIS rasters and verify statistics
    tiles_data = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(
            """
            SELECT
                ST_Width(rast) as width,
                ST_Height(rast) as height
            FROM processing.dem
            ORDER BY ST_XMin(ST_Envelope(rast)), ST_YMin(ST_Envelope(rast))
            """
        )
    ).all()

    assert len(tiles_data) == 4, f"Expected 4 tiles, got {len(tiles_data)}"

    # Verify each tile is 256x256
    for tile_width, tile_height in tiles_data:
        assert tile_width == 256, f"Expected tile width 256, got {tile_width}"
        assert tile_height == 256, f"Expected tile height 256, got {tile_height}"

    # Dump tiles back to GeoTIFF and compare with input
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_path = tmp_path / "reconstructed.tif"

        # Query merged raster from PostGIS using ST_AsGDALRaster
        raster_binary = processing_worker_session.exec(  # type: ignore[call-overload]
            sa.text(
                """
                SELECT ST_AsGDALRaster(
                    ST_Union(rast),
                    'GTiff'
                ) as geotiff_data
                FROM processing.dem
                """
            )
        ).first()[0]

        # Write the binary raster data to file
        if raster_binary:
            output_path.write_bytes(raster_binary)

            # Read the reconstructed raster
            with rasterio.open(str(output_path)) as reconstructed_src:
                reconstructed_array = reconstructed_src.read(1)
                reconstructed_crs = reconstructed_src.crs

            # Compare with input
            assert reconstructed_array.shape == input_array.shape, (
                f"Shape mismatch: {reconstructed_array.shape} vs {input_array.shape}"
            )

            assert np.allclose(
                reconstructed_array, input_array, rtol=1e-6, equal_nan=True
            ), "Reconstructed raster does not match input"

            assert reconstructed_crs == input_crs, (
                f"CRS mismatch: {reconstructed_crs} vs {input_crs}"
            )
