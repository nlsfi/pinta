# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
import pytest

from pinta_processing import core
from pinta_processing.filters import RoundValues
from pinta_processing_test_utils import constants


@pytest.mark.parametrize(
    ("precision", "expected"),
    [
        (
            0,
            np.array(
                [[1, constants.DEFAULT_NODATA], [3, 5]],
                dtype=constants.DEFAULT_DTYPE,
            ),
        ),
        (
            1,
            np.array(
                [[1.0, constants.DEFAULT_NODATA], [3.3, 4.6]],
                dtype=constants.DEFAULT_DTYPE,
            ),
        ),
        (
            2,
            np.array(
                [[1.00, constants.DEFAULT_NODATA], [3.33, 4.56]],
                dtype=constants.DEFAULT_DTYPE,
            ),
        ),
        (
            3,
            np.array(
                [[1.000, constants.DEFAULT_NODATA], [3.333, 4.556]],
                dtype=constants.DEFAULT_DTYPE,
            ),
        ),
    ],
    ids=[
        "precision-0",
        "precision-1",
        "precision-2",
        "precision-3",
    ],
)
def test_round(precision: int, expected: np.ndarray):
    dataset = core.RasterDataset(
        array=np.array(
            [[1.0, constants.DEFAULT_NODATA], [3.3333333, 4.555555]],
            dtype=constants.DEFAULT_DTYPE,
        ),
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )

    stage = RoundValues(precision=precision)
    result = stage.process(dataset)

    assert np.array_equal(result.array, expected)
