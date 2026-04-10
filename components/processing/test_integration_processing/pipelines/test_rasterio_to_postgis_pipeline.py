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
from rasterio.transform import Affine

from pinta_processing import core, pipelines, reader, writer

if typing.TYPE_CHECKING:
    from sqlmodel import Session


def test_postgis_writer(processing_worker_session: "Session") -> None:
    raster.initialize_raster_table(processing_worker_session, "processing", "dem")
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


def test_postgis_writer_with_staging_tables(
    processing_worker_session: "Session",
) -> None:
    """Test PostgisWriter with staging tables and verify data distribution and counts.

    Generate 10 random rasters, write to db using 3 staging tables."""

    def get_pipeline(file_path: Path) -> core.Pipeline:
        return reader.RasterioReader(str(file_path)) | writer.PostgisWriter(
            "processing", "dem", processing_worker_session, staging_tables=3
        )

    raster.initialize_raster_table(
        processing_worker_session, "processing", "dem", staging_tables=3
    )

    # Generate 10 512x512 random rasters inside finland extents (use epsg:3067) to tmp geotiffs
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        file_paths = []

        # Finland EPSG:3067 bounds (approximate)
        # We'll create tiles across different regions to distribute to staging tables
        start_x = 100000.0
        start_y = 6000000.0
        tile_spacing = 100000.0

        # Create random number generator with fixed seed for reproducibility
        rng = np.random.default_rng(1337)

        for i in range(10):
            # Create a random 512x512 raster
            raster_data = rng.random((512, 512), dtype=np.float32)

            # Calculate position in the grid
            grid_row = i // 5
            grid_col = i % 5

            # Create transform for this tile
            ulx = start_x + grid_col * tile_spacing
            uly = start_y + grid_row * tile_spacing

            transform = Affine.translation(ulx, uly) * Affine.scale(2.0, -2.0)

            # Write to GeoTIFF
            file_path = tmp_path / f"raster_{i:02d}.tif"
            with rasterio.open(
                str(file_path),
                "w",
                driver="GTiff",
                height=512,
                width=512,
                count=1,
                dtype=raster_data.dtype,
                crs="EPSG:3067",
                transform=transform,
                nodata=None,
            ) as dst:
                dst.write(raster_data, 1)

            file_paths.append(file_path)

        # Loop files and for each file call get_pipeline and execute
        for file_path in file_paths:
            pipeline = get_pipeline(file_path)
            pipeline.execute()

    # Assert that "processing"."dem" has 0 rows and each staging table has rows
    main_table_count = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text("SELECT COUNT(*) FROM processing.dem")
    ).first()[0]
    assert main_table_count == 0, (
        f"Expected main table to have 0 rows, got {main_table_count}"
    )

    # Assert staging table counts
    expected_counts = {"dem_p0": 12, "dem_p1": 12, "dem_p2": 16}
    for i in range(3):
        staging_table = f"dem_p{i}"
        count_result = processing_worker_session.exec(  # type: ignore[call-overload]
            sa.text(f"SELECT COUNT(*) FROM processing.{staging_table}")
        ).first()[0]
        assert count_result == expected_counts[staging_table], (
            f"Expected {expected_counts[staging_table]} rows in {staging_table}, got {count_result}"
        )


def test_rasterio_to_postgis(
    processing_worker_session: "Session",
) -> None:

    table_name = "test_raster_ol"
    schema = "processing"
    staging_tables = 2
    ol_2_name = f"o_2_{table_name}"
    ol_8_name = f"o_8_{table_name}"
    ol_128_name = f"o_128_{table_name}"

    raster.initialize_raster_table(
        processing_worker_session, schema, table_name, staging_tables
    )
    raster.initialize_overview_tables(
        processing_worker_session, schema, table_name, staging_tables
    )

    file_path = pinta_utils.get_test_data_path("processing/dem.asc.zip")
    pipeline = pipelines.rasterio_to_postgis(
        processing_worker_session, file_path, schema, table_name, staging_tables
    )
    pipeline.execute()

    raster.merge_staging_tables(
        schema, table_name, staging_tables, processing_worker_session
    )
    raster.merge_staging_tables(
        schema, ol_2_name, staging_tables, processing_worker_session
    )
    raster.merge_staging_tables(
        schema, ol_8_name, staging_tables, processing_worker_session
    )
    raster.merge_staging_tables(
        schema, ol_128_name, staging_tables, processing_worker_session
    )
    raster.finalize_overview_tables(processing_worker_session, schema, table_name)

    # Verify 4 tiles were written to database
    tile_count_result = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{table_name}")
    ).first()
    assert tile_count_result == (4,), f"Expected 4 tiles, got {tile_count_result[0]}"

    # Verify overlay 2 tiles were written to database
    ol_2_count_result = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{ol_2_name}")
    ).first()
    assert ol_2_count_result == (1,), f"Expected 1 tile, got {ol_2_count_result[0]}"

    # Verify overlay 8 tiles were written to database
    ol_8_count_result = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{ol_8_name}")
    ).first()
    assert ol_8_count_result == (1,), f"Expected 1 tile, got {ol_8_count_result[0]}"

    # Verify overlay 128 tiles were written to database
    ol_128_count_result = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{ol_128_name}")
    ).first()
    assert ol_128_count_result == (1,), f"Expected 1 tile, got {ol_128_count_result[0]}"
