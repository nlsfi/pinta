# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np
import pytest

from pinta_processing import core

DEFAULT_CRS = "EPSG:3067"
DEFAULT_TRANSFORM = affine.Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)
DEFAULT_DTYPE = np.float32
DEFAULT_NODATA = -9999.0


@pytest.fixture
def default_transform() -> affine.Affine:
    """Standard identity-like affine transform."""
    return DEFAULT_TRANSFORM


@pytest.fixture
def dataset() -> core.RasterDataset:
    """RasterDataset with georeferencing and nodata value."""
    array = np.array([[1.0, DEFAULT_NODATA], [3.0, 4.0]], dtype=DEFAULT_DTYPE)
    return core.RasterDataset(
        array=array,
        transform=DEFAULT_TRANSFORM,
        crs=DEFAULT_CRS,
        nodata=DEFAULT_NODATA,
    )
