# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import RasterFilter
from pinta_processing_test_utils import constants


def test_raster_filter_applies_predicate(dataset: core.RasterDataset):
    stage = RasterFilter(predicate=lambda x: np.abs(x) > 1)
    result = stage.process(dataset)

    expected = np.array(
        [
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [3.0, 4.0],
        ],
        dtype=constants.DEFAULT_DTYPE,
    )
    assert np.allclose(result.array, expected)


def test_raster_filter_preserves_metadata(dataset: core.RasterDataset):
    stage = RasterFilter(predicate=lambda x: x > 1)
    result = stage.process(dataset)

    assert result.transform == dataset.transform
    assert result.crs == dataset.crs
    assert result.nodata == dataset.nodata


def test_raster_filter_excludes_existing_nodata_from_predicate():
    array = np.array([[1.0, constants.DEFAULT_NODATA], [3.0, -4.0]], dtype=np.float32)
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = RasterFilter(predicate=lambda x: np.abs(x) > 1)
    result = stage.process(dataset)

    expected = np.array(
        [[constants.DEFAULT_NODATA, constants.DEFAULT_NODATA], [3.0, -4.0]],
        dtype=np.float32,
    )
    assert np.allclose(result.array, expected)


def test_raster_filter_without_nodata_uses_nan():
    array = np.array([[1, 2], [3, 4]], dtype=np.int16)
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=None,
    )
    stage = RasterFilter(predicate=lambda x: x > 2)
    result = stage.process(dataset)

    assert np.isnan(result.nodata)
    assert result.array.dtype == np.float32
    assert np.isnan(result.array[0, 0])
    assert np.isnan(result.array[0, 1])
    assert np.allclose(result.array[1], np.array([3.0, 4.0]))


def test_raster_filter_invalid_input():
    stage = RasterFilter(predicate=lambda x: x > 1)

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process("not a dataset")

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(None)


def test_raster_filter_rejects_predicate_with_invalid_shape(
    dataset: core.RasterDataset,
):
    def predicate(_: np.ndarray) -> np.ndarray:
        return np.array([True, False])

    stage = RasterFilter(predicate=predicate)

    with pytest.raises(ValueError, match="same shape"):
        stage.process(dataset)


def test_raster_filter_does_not_modify_input(dataset: core.RasterDataset):
    original = dataset.array.copy()

    stage = RasterFilter(predicate=lambda x: x > 1)
    stage.process(dataset)

    assert np.allclose(dataset.array, original)
