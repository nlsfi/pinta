# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

import affine
import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import RasterUnion
from pinta_processing_test_utils import constants

_TRANSFORM = affine.Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)


def _dataset(
    array: np.ndarray,
    *,
    transform: affine.Affine = _TRANSFORM,
    crs: str = constants.DEFAULT_CRS,
    nodata: float | None = None,
) -> core.RasterDataset:
    return core.RasterDataset(
        array=np.asarray(array, dtype=np.float32),
        transform=transform,
        crs=crs,
        nodata=nodata,
    )


def test_union_last_dataset_wins_on_overlap():
    first = _dataset(np.full((2, 2), 1.0))
    second = _dataset(np.full((2, 2), 2.0))
    third = _dataset(np.full((2, 2), 3.0))

    result = RasterUnion().process((first, second, third))

    assert np.allclose(result.array, 3.0)


def test_union_fills_from_earlier_where_later_is_nodata():
    first = _dataset(np.full((2, 2), 1.0))
    second_array = np.array([[2.0, constants.DEFAULT_NODATA], [2.0, 2.0]])
    second = _dataset(second_array, nodata=constants.DEFAULT_NODATA)

    result = RasterUnion().process((first, second))

    # Later dataset wins everywhere except its nodata cell, kept from the first.
    expected = np.array([[2.0, 1.0], [2.0, 2.0]])
    assert np.allclose(result.array, expected)


def test_union_combines_disjoint_extents():
    # Left raster covers columns 0..1, right raster columns 2..3.
    left = _dataset(np.full((2, 2), 1.0))
    right_transform = affine.Affine(1.0, 0.0, 2.0, 0.0, -1.0, 0.0)
    right = _dataset(np.full((2, 2), 2.0), transform=right_transform)

    result = RasterUnion().process((left, right))

    assert result.array.shape == (2, 4)
    assert result.transform == _TRANSFORM
    assert np.allclose(result.array[:, :2], 1.0)
    assert np.allclose(result.array[:, 2:], 2.0)


def test_union_extends_extent_and_overlaps():
    # Base covers columns 0..2, overlay columns 1..3, overlapping on column 1..2.
    base = _dataset(np.full((2, 3), 1.0))
    overlay_transform = affine.Affine(1.0, 0.0, 1.0, 0.0, -1.0, 0.0)
    overlay = _dataset(np.full((2, 3), 2.0), transform=overlay_transform)

    result = RasterUnion().process((base, overlay))

    assert result.array.shape == (2, 4)
    # Column 0 only from base, columns 1..3 from the winning overlay.
    expected = np.array([1.0, 2.0, 2.0, 2.0])
    assert np.allclose(result.array, np.tile(expected, (2, 1)))


def test_union_fills_gaps_with_nodata():
    # Two disjoint rasters leave the opposite corners uncovered.
    top_left = _dataset(np.full((2, 2), 5.0), nodata=constants.DEFAULT_NODATA)
    bottom_right_transform = affine.Affine(1.0, 0.0, 2.0, 0.0, -1.0, -2.0)
    bottom_right = _dataset(
        np.full((2, 2), 7.0),
        transform=bottom_right_transform,
        nodata=constants.DEFAULT_NODATA,
    )

    result = RasterUnion().process((top_left, bottom_right))

    assert result.array.shape == (4, 4)
    assert result.nodata == constants.DEFAULT_NODATA
    # Uncovered cells are filled with nodata.
    assert result.array[0, 2] == constants.DEFAULT_NODATA
    assert result.array[2, 0] == constants.DEFAULT_NODATA
    assert result.array[0, 0] == 5.0
    assert result.array[2, 2] == 7.0


def test_union_single_dataset_returns_equivalent_raster():
    only = _dataset(np.array([[1.0, 2.0], [3.0, 4.0]]))

    result = RasterUnion().process((only,))

    assert np.allclose(result.array, only.array)
    assert result.transform == only.transform


def test_union_preserves_crs():
    first = _dataset(np.full((2, 2), 1.0), crs="EPSG:3067")
    second = _dataset(np.full((2, 2), 2.0), crs="EPSG:3067")

    result = RasterUnion().process((first, second))

    assert result.crs == "EPSG:3067"


def test_union_does_not_modify_inputs():
    first = _dataset(np.full((2, 2), 1.0))
    second = _dataset(np.full((2, 2), 2.0))
    original_first = first.array.copy()
    original_second = second.array.copy()

    RasterUnion().process((first, second))

    assert np.allclose(first.array, original_first)
    assert np.allclose(second.array, original_second)


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a tuple",
        None,
        (),
        (_dataset(np.zeros((2, 2))), "not a dataset"),
    ],
    ids=["string", "none", "empty-tuple", "non-dataset-member"],
)
def test_union_invalid_input_raises_error(invalid_input: Any):
    with pytest.raises(exceptions.InvalidStageInputError):
        RasterUnion().process(invalid_input)


def test_union_rejects_mismatched_crs():
    first = _dataset(np.full((2, 2), 1.0), crs="EPSG:3067")
    second = _dataset(np.full((2, 2), 2.0), crs="EPSG:4326")

    with pytest.raises(ValueError, match="same CRS"):
        RasterUnion().process((first, second))


def test_union_rejects_mismatched_pixel_size():
    first = _dataset(np.full((2, 2), 1.0))
    coarse_transform = affine.Affine(2.0, 0.0, 0.0, 0.0, -2.0, 0.0)
    second = _dataset(np.full((2, 2), 2.0), transform=coarse_transform)

    with pytest.raises(ValueError, match="same pixel size"):
        RasterUnion().process((first, second))
