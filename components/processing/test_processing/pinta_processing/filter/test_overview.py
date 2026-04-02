# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import DownsampleOverview
from pinta_processing_test_utils import constants


@pytest.fixture
def dataset_4x4() -> core.RasterDataset:
    array = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ],
        dtype=np.float32,
    )
    return core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_downsample_overview_averages_blocks(factor: int):
    array = np.arange(1, 257, dtype=np.float32).reshape(16, 16)
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = DownsampleOverview(factor=factor)
    result = stage.process(dataset)

    n = 16 // factor
    expected = array.reshape(n, factor, n, factor).mean(axis=(1, 3))
    assert result.array.shape == (n, n)
    assert np.allclose(result.array, expected)


def test_downsample_overview_excludes_nodata_from_average():
    array = np.array(
        [
            [1.0, constants.DEFAULT_NODATA, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ],
        dtype=np.float32,
    )
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset)

    expected = np.array([[4.0, 5.5], [11.5, 13.5]], dtype=np.float32)
    assert np.allclose(result.array, expected)


def test_downsample_overview_all_nodata_block_returns_nodata():
    array = np.array(
        [
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 3.0, 4.0],
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ],
        dtype=np.float32,
    )
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset)

    assert result.array[0, 0] == constants.DEFAULT_NODATA
    assert np.allclose(result.array[0, 1], 5.5)


def test_downsample_overview_none_input_returns_none():
    stage = DownsampleOverview(factor=2)
    result = stage.process(None)

    assert result is None


def test_downsample_overview_invalid_input_raises_error():
    stage = DownsampleOverview(factor=2)

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process("not a dataset")


def test_downsample_overview_scales_transform(dataset_4x4: core.RasterDataset):
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset_4x4)

    expected_transform = affine.Affine(2.0, 0.0, 0.0, 0.0, -2.0, 0.0)
    assert result.transform == expected_transform


def test_downsample_overview_preserves_metadata(dataset_4x4: core.RasterDataset):
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset_4x4)

    assert result.crs == dataset_4x4.crs
    assert result.nodata == dataset_4x4.nodata


def test_downsample_overview_preserves_dtype(dataset_4x4: core.RasterDataset):
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset_4x4)

    assert result.array.dtype == dataset_4x4.array.dtype


def test_downsample_overview_without_nodata():
    array = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ],
        dtype=np.float32,
    )
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=None,
    )
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset)

    expected = np.array([[3.5, 5.5], [11.5, 13.5]], dtype=np.float32)
    assert np.allclose(result.array, expected)
    assert result.nodata is None


def test_downsample_overview_includes_all_pixels_for_non_divisible_dimensions():
    # 5x5 — output is 5//2=2x2; each pixel covers 2.5x2.5 input pixels
    array = np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [6.0, 7.0, 8.0, 9.0, 10.0],
            [11.0, 12.0, 13.0, 14.0, 15.0],
            [16.0, 17.0, 18.0, 19.0, 20.0],
            [21.0, 22.0, 23.0, 24.0, 25.0],
        ],
        dtype=np.float32,
    )
    dataset = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    stage = DownsampleOverview(factor=2)
    result = stage.process(dataset)

    assert result.array.shape == (2, 2)
    expected = np.array([[5.8, 8.2], [17.8, 20.2]], dtype=np.float32)
    assert np.allclose(result.array, expected)
