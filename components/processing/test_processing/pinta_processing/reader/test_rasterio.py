# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import tempfile
import zipfile
from pathlib import Path

import pytest
import rasterio
from pinta_test_utils import pinta_utils

from pinta_processing import core, reader
from pinta_processing_test_utils import constants


def test_rasterio_reader():
    file_path = pinta_utils.get_test_data_path("processing/dem.tif")
    stage = reader.RasterioReader(file_path)
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.shape == (512, 512)
    assert dataset.transform is not None
    assert dataset.crs == constants.DEFAULT_CRS
    assert dataset.nodata == constants.DEFAULT_NODATA


def test_rasterio_reader_file_not_found():
    file_path = pinta_utils.get_test_data_path(
        "processing/non-existent-file.tif", check_if_exists=False
    )
    stage = reader.RasterioReader(file_path)
    with pytest.raises(rasterio.RasterioIOError):
        stage.process(None)


def test_rasterio_reader_from_zip():
    file_path = pinta_utils.get_test_data_path("processing/dem.asc.zip")
    stage = reader.RasterioReader(file_path)
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.shape == (512, 512)
    assert dataset.transform is not None
    assert dataset.crs is None  # asc file doesn't contain CRS info
    assert dataset.nodata == constants.DEFAULT_NODATA


@pytest.mark.parametrize(
    ("file_count", "error_match"),
    [
        (0, "No files found in zip archive"),
        (2, "Zip archive contains 2 files, expected exactly 1"),
    ],
)
def test_rasterio_reader_zip_invalid_contents(file_count: int, error_match: str):
    """Test that RasterioReader raises ValueError for invalid zip contents."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(file_count):
                zf.writestr(f"file{i}.txt", "dummy content")

        stage = reader.RasterioReader(zip_path)
        with pytest.raises(ValueError, match=error_match):
            stage.process(None)


def test_rasterio_reader_set_crs_when_no_crs():
    """Test that CRS is set when input raster has no CRS."""
    file_path = pinta_utils.get_test_data_path("processing/dem.asc.zip")
    crs_to_set = "EPSG:3067"

    stage = reader.RasterioReader(file_path, crs=crs_to_set)
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.crs == crs_to_set


def test_rasterio_reader_raises_on_crs_mismatch():
    """Test that reader raises when CRS differs from raster file CRS."""
    file_path = pinta_utils.get_test_data_path("processing/dem.tif")
    mismatched_crs = "EPSG:4326"

    stage = reader.RasterioReader(file_path, crs=mismatched_crs)
    with pytest.raises(NotImplementedError, match="CRS mismatch"):
        stage.process(None)
