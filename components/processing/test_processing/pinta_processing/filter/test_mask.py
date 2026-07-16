# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np
import pytest
from pinta_common import Settings
from shapely.geometry import box

from pinta_processing import core, exceptions
from pinta_processing.filters import RasterMask
from pinta_processing_test_utils import constants

# Transform maps pixel (row, col) centre to (col + 0.5, -(row + 0.5)).
_TRANSFORM = affine.Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)

_ELEVATION = 42.0


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


def test_mask_sets_polygon_pixels_to_elevation():
    dataset = _dataset(np.zeros((5, 5)))
    stage = RasterMask(_pixel_box_wkt(2, 3), _ELEVATION)

    result = stage.process(dataset)

    assert result.array[2, 3] == _ELEVATION


def test_mask_leaves_pixels_outside_polygon_untouched():
    dataset = _dataset(np.arange(25, dtype=np.float64).reshape((5, 5)))
    stage = RasterMask(_pixel_box_wkt(2, 3), _ELEVATION)

    result = stage.process(dataset)

    outside = np.ones((5, 5), dtype=bool)
    outside[2, 3] = False
    assert np.allclose(result.array[outside], dataset.array[outside])


def test_mask_only_covers_pixels_with_centre_inside_polygon():
    dataset = _dataset(np.zeros((5, 5)))
    # A box that overlaps four pixels but only contains the centre of one.
    stage = RasterMask(box(2.2, -3.2, 3.4, -2.2).wkt, _ELEVATION)

    result = stage.process(dataset)

    assert result.array[2, 2] == _ELEVATION
    assert np.count_nonzero(result.array) == 1


def test_mask_preserves_metadata_and_input():
    dataset = _dataset(np.zeros((5, 5)), nodata=constants.DEFAULT_NODATA)
    original = dataset.array.copy()
    stage = RasterMask(_pixel_box_wkt(2, 3), _ELEVATION)

    result = stage.process(dataset)

    assert result.transform == dataset.transform
    assert result.crs == constants.DEFAULT_CRS
    assert result.nodata == constants.DEFAULT_NODATA
    assert np.allclose(dataset.array, original)


def test_mask_without_input_creates_dataset_from_scratch():
    # A polygon covering 4x2 DEM pixels, offset from the pixel lattice so the
    # created grid must snap outward to it.
    pixel_size = Settings.DB_DEM_PIXEL_SIZE
    polygon = box(
        100 * pixel_size + 0.5,
        50 * pixel_size + 0.5,
        104 * pixel_size - 0.5,
        52 * pixel_size - 0.5,
    )
    stage = RasterMask(polygon.wkt, _ELEVATION)

    result = stage.process(None)

    assert result.crs == f"EPSG:{Settings.DB_SRID}"
    assert result.nodata == Settings.DB_DEM_NODATA
    # The grid snaps outward to the DEM pixel lattice around the polygon.
    assert result.bounds == (
        100 * pixel_size,
        50 * pixel_size,
        104 * pixel_size,
        52 * pixel_size,
    )
    assert result.transform.a == pixel_size
    assert result.transform.e == -pixel_size
    # Every pixel centre falls inside the polygon, so all pixels are masked.
    assert np.all(result.array == _ELEVATION)


def test_mask_without_input_fills_outside_polygon_with_nodata():
    pixel_size = Settings.DB_DEM_PIXEL_SIZE
    # A triangle inside a 4x4 pixel bounding box leaves nodata pixels behind.
    triangle = (
        f"POLYGON ((0 0, {4 * pixel_size} 0, {4 * pixel_size} {4 * pixel_size}, 0 0))"
    )
    stage = RasterMask(triangle, _ELEVATION)

    result = stage.process(None)

    assert np.any(result.array == _ELEVATION)
    assert np.any(result.array == Settings.DB_DEM_NODATA)
    assert np.all(np.isin(result.array, [_ELEVATION, Settings.DB_DEM_NODATA]))


@pytest.mark.parametrize(
    "invalid_wkt",
    [
        "POINT (1 1)",
        "LINESTRING (0 0, 1 1)",
        "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)))",
    ],
)
def test_mask_rejects_non_polygon_geometry(invalid_wkt: str):
    with pytest.raises(ValueError, match="must be a Polygon"):
        RasterMask(invalid_wkt, _ELEVATION)


def test_mask_rejects_unparseable_wkt():
    with pytest.raises(ValueError, match="could not be parsed"):
        RasterMask("not a wkt", _ELEVATION)


def test_mask_rejects_invalid_input_type():
    stage = RasterMask(_pixel_box_wkt(0, 0), _ELEVATION)

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process("not a dataset")  # type: ignore[arg-type]
