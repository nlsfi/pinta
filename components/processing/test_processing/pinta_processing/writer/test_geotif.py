# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pathlib

import affine
import numpy as np
import pytest
import rasterio

from pinta_processing import core, exceptions
from pinta_processing.writer import GeotiffWriter


def test_geotiff_writer(
    tmp_path: pathlib.Path,
    dataset: core.RasterDataset,
    default_transform: affine.Affine,
):
    """Test write with full georeferencing and nodata preservation."""
    output_path = tmp_path / "output.tif"

    stage = GeotiffWriter(str(output_path))
    stage.process(dataset)

    # Verify file was written
    assert output_path.exists()

    # Verify contents with full metadata
    with rasterio.open(str(output_path)) as src:
        assert src.shape == (2, 2)
        assert src.crs == "EPSG:3067"
        assert src.transform == default_transform
        assert src.nodata == -9999.0
        assert np.allclose(src.read(1), dataset.array)
        # Verify nodata value is preserved
        assert src.read(1)[0, 1] == -9999.0


def test_geotiff_writer_invalid_input(tmp_path: pathlib.Path):
    """Test that invalid input raises InvalidStageInputError."""
    output_path = tmp_path / "output.tif"
    stage = GeotiffWriter(str(output_path))

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process("not a dataset")

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(None)


def test_geotiff_writer_overwrites_existing_file(
    tmp_path: pathlib.Path, default_transform: affine.Affine
):
    """Test that writer overwrites existing files."""
    output_path = tmp_path / "output_overwrite.tif"
    # Create initial file
    array1 = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    dataset1 = core.RasterDataset(
        array=array1, transform=default_transform, crs="EPSG:3067", nodata=None
    )

    stage1 = GeotiffWriter(str(output_path))
    stage1.process(dataset1)

    # Overwrite with different data
    array2 = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)
    dataset2 = core.RasterDataset(
        array=array2, transform=default_transform, crs="EPSG:3067", nodata=None
    )

    stage2 = GeotiffWriter(str(output_path))
    stage2.process(dataset2)

    with rasterio.open(str(output_path)) as src:
        assert np.allclose(src.read(1), array2)
