# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
import rasterio
from pinta_test_utils import pinta_utils

from pinta_processing import core, reader


def test_rasterio_reader(pytestconfig: pytest.Config):
    file_path = pinta_utils.get_test_data_path(pytestconfig, "processing/dem.tif")
    stage = reader.RasterioReader(file_path)
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.shape == (512, 512)
    assert dataset.transform is not None
    assert dataset.crs == "EPSG:3067"
    assert dataset.nodata == -9999


def test_rasterio_reader_file_not_found(pytestconfig: pytest.Config):
    file_path = pinta_utils.get_test_data_path(
        pytestconfig, "processing/non-existent-file.tif"
    )
    stage = reader.RasterioReader(file_path)
    with pytest.raises(rasterio.RasterioIOError):
        stage.process(None)
