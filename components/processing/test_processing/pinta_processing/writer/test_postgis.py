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
from pinta_processing.filters import DownsampleOverview
from pinta_processing.writer import RasterPostgisWriter, VectorPostgisWriter, WriterMode


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


def _mock_update_session(mocker: MockerFixture) -> tuple:
    """Session whose raw connection exposes cursor/copy as context managers."""
    session = mocker.MagicMock()
    raw_connection = session.connection.return_value.connection
    cursor = raw_connection.cursor.return_value.__enter__.return_value
    cursor.copy.return_value.__enter__.return_value = mocker.MagicMock()
    return session, raw_connection, cursor


def test_generate_tiles_returns_empty_for_zero_sized_raster():
    """A degenerate raster (zero-sized dimension) yields no tiles."""
    empty = core.RasterDataset(
        array=np.empty((0, 0), dtype=np.float32),
        transform=Affine.identity(),
        crs="EPSG:3067",
        nodata=-9999.0,
    )
    stage = RasterPostgisWriter("foo", "bar", None, tile_size=4)  # type: ignore[arg-type]

    assert stage._generate_tiles(empty) == []


def test_update_mode_skips_raster_downsampled_below_one_pixel(
    dataset: core.RasterDataset, mocker: MockerFixture
):
    """A small patch downsampled past its own size must not crash the writer.

    Reproduces the overview edge case: a tiny update-area patch downsampled for a
    high overview level (factor 128) collapses to a 0x0 raster, which previously
    raised a rasterio WindowError while tiling.
    """
    session, raw_connection, cursor = _mock_update_session(mocker)
    downsampled = DownsampleOverview(factor=128).process(dataset)
    assert downsampled is not None
    assert downsampled.array.size == 0  # 2x2 // 128 -> 0x0

    stage = RasterPostgisWriter(
        "myschema", "mytable", session, staging_tables=0, mode=WriterMode.UPDATE
    )
    stage.process(downsampled)

    cursor.execute.assert_not_called()
    raw_connection.commit.assert_not_called()
    raw_connection.rollback.assert_not_called()


def test_update_mode_rejects_staging_tables():
    """Update mode is only supported with staging_tables=0."""
    with pytest.raises(ValueError, match="staging_tables"):
        RasterPostgisWriter(
            "foo", "bar", None, staging_tables=1, mode=WriterMode.UPDATE
        )  # type: ignore[arg-type]


def test_update_mode_merges_and_commits(
    dataset: core.RasterDataset, mocker: MockerFixture
):
    """Update mode stages tiles, runs merge + insert, and commits once."""
    session, raw_connection, cursor = _mock_update_session(mocker)

    stage = RasterPostgisWriter(
        "myschema",
        "mytable",
        session,
        staging_tables=0,
        tile_size=4,
        mode=WriterMode.UPDATE,
    )
    stage.process(dataset)

    executed_sql = " ".join(str(call.args[0]) for call in cursor.execute.call_args_list)
    assert "CREATE TEMP TABLE" in executed_sql
    assert "ST_MapAlgebra" in executed_sql
    assert "INSERT INTO myschema.mytable" in executed_sql

    raw_connection.commit.assert_called_once()
    raw_connection.rollback.assert_not_called()


def test_update_mode_skips_all_nodata_data(
    dataset: core.RasterDataset, mocker: MockerFixture
):
    """A fully nodata input stages nothing and merges nothing."""
    session, raw_connection, cursor = _mock_update_session(mocker)
    nodata_dataset = core.RasterDataset(
        array=np.full_like(dataset.array, dataset.nodata),
        transform=dataset.transform,
        crs=dataset.crs,
        nodata=dataset.nodata,
    )

    stage = RasterPostgisWriter(
        "myschema",
        "mytable",
        session,
        staging_tables=0,
        tile_size=4,
        mode=WriterMode.UPDATE,
    )
    stage.process(nodata_dataset)

    cursor.execute.assert_not_called()
    raw_connection.commit.assert_not_called()
    raw_connection.rollback.assert_not_called()


def test_update_mode_rolls_back_on_failure(
    dataset: core.RasterDataset, mocker: MockerFixture
):
    """A failure mid-write rolls back so no half-updated rows remain."""
    session, raw_connection, cursor = _mock_update_session(mocker)
    cursor.execute.side_effect = [None, RuntimeError("merge failed")]

    stage = RasterPostgisWriter(
        "myschema",
        "mytable",
        session,
        staging_tables=0,
        tile_size=4,
        mode=WriterMode.UPDATE,
    )

    with pytest.raises(RuntimeError, match="merge failed"):
        stage.process(dataset)

    raw_connection.rollback.assert_called_once()
    raw_connection.commit.assert_not_called()


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
