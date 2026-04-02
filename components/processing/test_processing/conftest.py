# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np
import pytest

from pinta_processing import core
from pinta_processing_test_utils import constants


@pytest.fixture
def default_transform() -> affine.Affine:
    """Standard identity-like affine transform."""
    return constants.DEFAULT_TRANSFORM


@pytest.fixture
def dataset() -> core.RasterDataset:
    """RasterDataset with georeferencing and nodata value."""
    array = np.array(
        [[1.0, constants.DEFAULT_NODATA], [3.0, 4.0]], dtype=constants.DEFAULT_DTYPE
    )
    return core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
