# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

import affine
import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import RasterDiff
from pinta_processing_test_utils import constants

_DATASET = core.RasterDataset(
    array=np.array([[5.0, 3.0], [8.0, 1.0]], dtype=np.float32),
    transform=constants.DEFAULT_TRANSFORM,
    crs=constants.DEFAULT_CRS,
    nodata=None,
)
_SECOND_DATASET = core.RasterDataset(
    array=np.array([[2.0, 1.0], [3.0, 4.0]], dtype=np.float32),
    transform=constants.DEFAULT_TRANSFORM,
    crs=constants.DEFAULT_CRS,
    nodata=constants.DEFAULT_NODATA,
)


@pytest.fixture
def first() -> core.RasterDataset:
    array = np.array([[5.0, 3.0], [8.0, 1.0]], dtype=np.float32)
    return core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=None,
    )


@pytest.fixture
def second() -> core.RasterDataset:
    array = np.array([[2.0, 1.0], [3.0, 4.0]], dtype=np.float32)
    return core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )


def test_raster_diff_subtracts_valid_pixels(
    first: core.RasterDataset, second: core.RasterDataset
):
    stage = RasterDiff()
    result = stage.process((first, second))

    expected = np.array([[3.0, 2.0], [5.0, -3.0]], dtype=np.float32)
    assert np.allclose(result.array, expected)


def test_raster_diff_first_nodata_masks_result(second: core.RasterDataset):
    array = np.array([[constants.DEFAULT_NODATA, 3.0], [8.0, 1.0]], dtype=np.float32)
    first = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = RasterDiff()
    result = stage.process((first, second))

    assert result.array[0, 0] == constants.DEFAULT_NODATA
    assert np.isclose(result.array[0, 1], 2.0)


def test_raster_diff_second_nodata_masks_result(first: core.RasterDataset):
    array = np.array([[constants.DEFAULT_NODATA, 1.0], [3.0, 4.0]], dtype=np.float32)
    second = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = RasterDiff()
    result = stage.process((first, second))

    assert result.array[0, 0] == constants.DEFAULT_NODATA
    assert np.isclose(result.array[0, 1], 2.0)


def test_raster_diff_either_nodata_masks_result():
    arr1 = np.array([[1.0, constants.DEFAULT_NODATA], [3.0, 4.0]], dtype=np.float32)
    arr2 = np.array([[constants.DEFAULT_NODATA, 2.0], [1.0, 4.0]], dtype=np.float32)
    first = core.RasterDataset(
        array=arr1,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    second = core.RasterDataset(
        array=arr2,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = RasterDiff()
    result = stage.process((first, second))

    assert result.array[0, 0] == constants.DEFAULT_NODATA
    assert result.array[0, 1] == constants.DEFAULT_NODATA
    assert np.isclose(result.array[1, 0], 2.0)
    assert np.isclose(result.array[1, 1], 0.0)


def test_raster_diff_result_nodata_from_first(second: core.RasterDataset):
    first_with_nodata = core.RasterDataset(
        array=np.array([[5.0, 3.0], [8.0, 1.0]], dtype=np.float32),
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = RasterDiff()
    result = stage.process((first_with_nodata, second))

    assert result.nodata == first_with_nodata.nodata


def test_raster_diff_result_nodata_from_second_when_first_has_none(
    first: core.RasterDataset, second: core.RasterDataset
):
    stage = RasterDiff()
    result = stage.process((first, second))

    assert result.nodata == second.nodata


def test_raster_diff_no_nodata_inputs(first: core.RasterDataset):
    second_no_nodata = core.RasterDataset(
        array=np.array([[2.0, 1.0], [3.0, 4.0]], dtype=np.float32),
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=None,
    )
    stage = RasterDiff()
    result = stage.process((first, second_no_nodata))

    expected = np.array([[3.0, 2.0], [5.0, -3.0]], dtype=np.float32)
    assert np.allclose(result.array, expected)
    assert result.nodata is None


def test_raster_diff_preserves_metadata(
    first: core.RasterDataset, second: core.RasterDataset
):
    stage = RasterDiff()
    result = stage.process((first, second))

    assert result.transform == first.transform
    assert result.crs == first.crs
    assert result.nodata == second.nodata


@pytest.mark.parametrize(
    ("first_raster", "second_raster", "match_string"),
    [
        (
            _DATASET,
            core.RasterDataset(
                array=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32),
                transform=constants.DEFAULT_TRANSFORM,
                crs=constants.DEFAULT_CRS,
                nodata=constants.DEFAULT_NODATA,
            ),
            "sizes",
        ),
        (
            _DATASET,
            core.RasterDataset(
                array=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
                transform=constants.DEFAULT_TRANSFORM,
                crs="EPSG:4326",
                nodata=constants.DEFAULT_NODATA,
            ),
            "CRS",
        ),
        (
            _DATASET,
            core.RasterDataset(
                array=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
                transform=affine.Affine(2.0, 0.0, 100.0, 0.0, -2.0, 200.0),
                crs=constants.DEFAULT_CRS,
                nodata=constants.DEFAULT_NODATA,
            ),
            "transform",
        ),
        (
            core.RasterDataset(
                array=np.array([[5, 3], [8, 1]], dtype=np.uint16),
                transform=constants.DEFAULT_TRANSFORM,
                crs=constants.DEFAULT_CRS,
                nodata=None,
            ),
            _SECOND_DATASET,
            "floating-point",
        ),
        (
            _DATASET,
            core.RasterDataset(
                array=np.array([[2, 1], [3, 4]], dtype=np.uint16),
                transform=constants.DEFAULT_TRANSFORM,
                crs=constants.DEFAULT_CRS,
                nodata=None,
            ),
            "floating-point",
        ),
        (
            _DATASET,
            core.RasterDataset(
                array=np.array([[2.0, 1.0], [3.0, 4.0]], dtype=np.float64),
                transform=constants.DEFAULT_TRANSFORM,
                crs=constants.DEFAULT_CRS,
                nodata=None,
            ),
            "identical",
        ),
    ],
    ids=[
        "shape-mismatch",
        "crs-mismatch",
        "transform-mismatch",
        "non-float-first",
        "non-float-second",
        "dtype-mismatch",
    ],
)
def test_raster_diff_raises_value_error(
    first_raster: core.RasterDataset,
    second_raster: core.RasterDataset,
    match_string: str,
):
    stage = RasterDiff()

    with pytest.raises(ValueError, match=match_string):
        stage.process((first_raster, second_raster))


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a tuple",
        None,
        (_DATASET,),
        (_DATASET, "not a dataset"),
        (_DATASET, _DATASET, _DATASET),
    ],
    ids=[
        "string",
        "none",
        "single-element-tuple",
        "non-dataset-second",
        "three-element-tuple",
    ],
)
def test_raster_diff_invalid_input_raises_error(invalid_input: Any):
    stage = RasterDiff()

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(invalid_input)


def test_raster_diff_does_not_modify_inputs(
    first: core.RasterDataset, second: core.RasterDataset
):
    original_first = first.array.copy()
    original_second = second.array.copy()

    stage = RasterDiff()
    stage.process((first, second))

    assert np.allclose(first.array, original_first)
    assert np.allclose(second.array, original_second)
