# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

import affine
import numpy as np
import pytest
from shapely.geometry import box

from pinta_processing import core, exceptions
from pinta_processing.filters import RasterInterpolate
from pinta_processing_test_utils import constants

# Transform maps pixel (row, col) centre to (col + 0.5, -(row + 0.5)).
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


def _pixel_box_wkt(row: int, col: int) -> str:
    """WKT box selecting the single pixel at (row, col)."""
    return box(col, -(row + 1), col + 1, -row).wkt


def _linear_field(rows: int, cols: int) -> np.ndarray:
    """A planar field z = row + col, exactly reproducible by cubic interpolation."""
    return np.fromfunction(lambda r, c: r + c, (rows, cols), dtype=np.float64)


def test_interpolate_replaces_polygon_pixels_from_surrounding_data():
    field = _linear_field(7, 7)
    corrupted = field.copy()
    corrupted[3, 3] = 999.0
    dataset = _dataset(corrupted)
    stage = RasterInterpolate(_pixel_box_wkt(3, 3))

    result = stage.process(dataset)

    # Cubic interpolation of a planar field recovers the true value ~= 6.0.
    assert np.isclose(result.array[3, 3], 6.0, atol=1e-3)


def test_interpolate_leaves_pixels_outside_polygon_untouched():
    field = _linear_field(7, 7)
    corrupted = field.copy()
    corrupted[3, 3] = 999.0
    dataset = _dataset(corrupted)
    stage = RasterInterpolate(_pixel_box_wkt(3, 3))

    result = stage.process(dataset)

    outside = np.ones((7, 7), dtype=bool)
    outside[3, 3] = False
    assert np.allclose(result.array[outside], corrupted[outside])


def test_interpolate_preserves_metadata():
    dataset = _dataset(_linear_field(7, 7), nodata=constants.DEFAULT_NODATA)
    stage = RasterInterpolate(_pixel_box_wkt(3, 3))

    result = stage.process(dataset)

    assert result.transform == dataset.transform
    assert result.crs == constants.DEFAULT_CRS
    assert result.nodata == constants.DEFAULT_NODATA


def test_interpolate_does_not_modify_input():
    field = _linear_field(7, 7)
    dataset = _dataset(field)
    original = dataset.array.copy()
    stage = RasterInterpolate(_pixel_box_wkt(3, 3))

    stage.process(dataset)

    assert np.allclose(dataset.array, original)


@pytest.mark.parametrize(
    "invalid_wkt",
    [
        "POINT (1 1)",
        "LINESTRING (0 0, 1 1)",
    ],
    ids=["point", "linestring"],
)
def test_interpolate_rejects_non_polygon(invalid_wkt: str):
    with pytest.raises(ValueError, match="Polygon"):
        RasterInterpolate(invalid_wkt)


def test_interpolate_rejects_unparseable_wkt():
    with pytest.raises(ValueError, match="could not be parsed"):
        RasterInterpolate("not wkt")


def test_interpolate_raises_when_polygon_covers_no_pixels():
    dataset = _dataset(_linear_field(5, 5))
    stage = RasterInterpolate(box(100, 100, 101, 101).wkt)

    with pytest.raises(ValueError, match="does not cover any raster pixels"):
        stage.process(dataset)


def test_interpolate_raises_when_data_does_not_surround_polygon():
    # Valid data only in the top rows, so a middle pixel is outside the
    # interpolation domain (no data below it).
    array = np.full((8, 8), constants.DEFAULT_NODATA, dtype=np.float32)
    array[0:2, :] = 10.0
    dataset = _dataset(array, nodata=constants.DEFAULT_NODATA)
    stage = RasterInterpolate(_pixel_box_wkt(4, 4))

    with pytest.raises(ValueError, match="too little data around the polygon"):
        stage.process(dataset)


def test_interpolate_raises_when_too_few_known_points():
    array = np.full((5, 5), constants.DEFAULT_NODATA, dtype=np.float32)
    array[0, 0] = 1.0
    array[0, 1] = 2.0
    dataset = _dataset(array, nodata=constants.DEFAULT_NODATA)
    stage = RasterInterpolate(_pixel_box_wkt(2, 2))

    with pytest.raises(ValueError, match="too little data around the polygon"):
        stage.process(dataset)


@pytest.mark.parametrize(
    "invalid_input",
    ["not a dataset", None, (_dataset(np.zeros((3, 3))),)],
    ids=["string", "none", "tuple"],
)
def test_interpolate_invalid_input_raises_error(invalid_input: Any):
    stage = RasterInterpolate(_pixel_box_wkt(1, 1))

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(invalid_input)
