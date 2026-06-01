# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import geopandas
import numpy as np
import pytest
from pytest_mock import MockerFixture
from rasterio.transform import Affine
from shapely.geometry import Point

from pinta_processing import core, exceptions
from pinta_processing.writer import RasterPostgisWriter, VectorPostgisWriter


@pytest.fixture
def vector_dataset() -> core.VectorDataset:
    """VectorDataset with a small GeoDataFrame."""
    gdf = geopandas.GeoDataFrame(
        {"value": [1.0, 2.0]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:3067",
    )
    return core.VectorDataset(geodataframe=gdf)


def test_postgis_writer_generate_tiles(dataset: core.RasterDataset):
    """Test that _generate_tiles creates tiles correctly from a RasterDataset."""
    # Create writer with small tile size for testing (4x4 tiles)
    stage = RasterPostgisWriter("foo", "bar", None, tile_size=4)  # type: ignore[call-arg]

    # Generate tiles from the 2x2 dataset
    tiles = stage._generate_tiles(dataset)

    # With a 2x2 dataset and 4x4 tile size, should produce exactly 1 tile
    assert len(tiles) == 1

    tile = tiles[0]
    assert isinstance(tile, core.RasterDataset)

    # Tile should preserve metadata
    assert tile.crs == dataset.crs
    assert tile.nodata == dataset.nodata

    # Tile should be the fixed size (4x4)
    assert tile.array.shape == (4, 4)

    # The 2x2 dataset data should be in the top-left of the tile, rest should be nodata
    assert tile.array[0, 0] == dataset.array[0, 0]
    assert tile.array[1, 1] == dataset.array[1, 1]
    assert np.all(np.isnan(tile.array[2:, :]) | (tile.array[2:, :] == dataset.nodata))


def test_postgis_writer_generates_multiple_tiles(dataset: core.RasterDataset):
    """Test that _generate_tiles creates multiple tiles for larger datasets."""
    # Create a larger dataset (8x8)
    large_array = np.arange(64, dtype=np.float32).reshape(8, 8)
    large_dataset = core.RasterDataset(
        array=large_array,
        transform=dataset.transform,
        crs=dataset.crs,
        nodata=dataset.nodata,
    )

    # Create writer with 4x4 tile size
    stage = RasterPostgisWriter("foo", "bar", None, tile_size=4)  # type: ignore[call-arg]

    # Generate tiles
    tiles = stage._generate_tiles(large_dataset)

    # Should produce exactly 4 tiles (2x2 grid) for 8x8 data with 4x4 tiles
    assert len(tiles) == 4

    # Verify all tiles are RasterDataset instances with correct size and metadata
    for tile in tiles:
        assert isinstance(tile, core.RasterDataset)
        assert tile.array.shape == (4, 4)
        assert tile.crs == dataset.crs
        assert tile.nodata == dataset.nodata

    # Verify that all original array values are present in the tiles
    tile_values = []
    for tile in tiles:
        # Get non-nodata values from this tile
        mask = tile.array != tile.nodata
        values = tile.array[mask]
        tile_values.extend(values.tolist())

    # Original array values should be present in the tiles
    original_values = set(large_array.flatten().tolist())
    tile_values_set = set(tile_values)

    # All original values should be present
    assert original_values == tile_values_set, (
        f"Missing values: {original_values - tile_values_set}, "
        f"Extra values: {tile_values_set - original_values}"
    )
    # Verify no data loss
    assert len(tile_values) == len(large_array.flatten())


def test_resolve_partition(dataset: core.RasterDataset):
    """Test that _resolve_partition returns valid partition index."""
    staging_tables = 3
    stage = RasterPostgisWriter("foo", "bar", None, staging_tables=staging_tables)  # type: ignore[call-arg]

    partition = stage._resolve_partition(dataset)

    # Partition should be in valid range [0, staging_tables - 1]
    assert 0 <= partition < staging_tables

    # Should be deterministic
    assert partition == stage._resolve_partition(dataset)


def test_resolve_partition_different_locations(dataset: core.RasterDataset):
    """Test that different spatial locations get correct partitions with deterministic seed."""
    staging_tables = 3
    stage = RasterPostgisWriter("foo", "bar", None, staging_tables=staging_tables)  # type: ignore[call-arg]

    # Create random number generator with fixed seed for reproducibility
    rng = np.random.default_rng(1337)

    # Expected partition for each dataset
    expected_partitions = [
        1,  # dataset 0
        2,  # dataset 1
        1,  # ...
        1,
        0,
        2,
        2,
        2,
        1,
        2,
    ]

    # Generate 10 random datasets at different locations
    for i in range(10):
        # Create dataset with random raster data and different location
        raster_data = rng.random((512, 512), dtype=np.float32)
        transform = Affine.translation(i * 100000, i * 100000) * Affine.scale(2.0, -2.0)

        test_dataset = core.RasterDataset(
            array=raster_data,
            transform=transform,
            crs=dataset.crs,
            nodata=dataset.nodata,
        )

        partition = stage._resolve_partition(test_dataset)

        assert partition == expected_partitions[i], (
            f"Dataset {i}: expected partition {expected_partitions[i]}, got {partition}"
        )


def test_vector_postgis_writer_writes_to_postgis(
    vector_dataset: core.VectorDataset, mocker: MockerFixture
):
    """Test that VectorPostgisWriter calls to_postgis with correct arguments."""
    mock_session = mocker.MagicMock()
    mock_inspector = mocker.MagicMock()
    mock_inspector.has_table.return_value = True
    mocker.patch("sqlalchemy.inspect", return_value=mock_inspector)

    mock_to_postgis = mocker.patch.object(
        geopandas.GeoDataFrame, "to_postgis", return_value=None
    )

    stage = VectorPostgisWriter("myschema", "mytable", mock_session)
    stage.process(vector_dataset)

    mock_to_postgis.assert_called_once_with(
        "mytable",
        mock_session.connection(),
        schema="myschema",
        if_exists="append",
        index=False,
    )


def test_vector_postgis_writer_invalid_input_raises_error(
    dataset: core.RasterDataset, mocker: MockerFixture
):
    """Test that passing a non-VectorDataset raises InvalidStageInputError."""
    mock_session = mocker.MagicMock()
    stage = VectorPostgisWriter("myschema", "mytable", mock_session)

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(dataset)  # type: ignore[arg-type]
