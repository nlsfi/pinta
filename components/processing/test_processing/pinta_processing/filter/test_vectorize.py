# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import VectorizeRaster
from pinta_processing_test_utils import constants


def _make_dataset(array: np.ndarray) -> core.RasterDataset:
    return core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )


def test_vectorize_raster_returns_vector_dataset():
    """VectorizeRaster returns a VectorDataset with a relevance_score column."""
    array = np.array(
        [
            [1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
        ],
        dtype=constants.DEFAULT_DTYPE,
    )
    result = VectorizeRaster().process(_make_dataset(array))

    assert isinstance(result, core.VectorDataset)
    assert "relevance_score" in result.geodataframe.columns


def test_vectorize_raster_produces_one_polygon_per_cluster():
    """Two spatially separated clusters produce two polygons."""
    array = np.array(
        [
            [1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 2.0, 2.0],
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 2.0, 2.0],
        ],
        dtype=constants.DEFAULT_DTYPE,
    )
    result = VectorizeRaster().process(_make_dataset(array))

    assert len(result.geodataframe) == 2


def test_vectorize_raster_nodata_only_input_returns_empty_geodataframe():
    """A raster containing only nodata values produces no polygons."""
    array = np.full((3, 3), constants.DEFAULT_NODATA, dtype=constants.DEFAULT_DTYPE)
    result = VectorizeRaster().process(_make_dataset(array))

    assert len(result.geodataframe) == 0


def test_vectorize_raster_relevance_score_is_non_negative():
    """relevance_score values are non-negative for all produced polygons."""
    array = np.array(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
        dtype=constants.DEFAULT_DTYPE,
    )
    result = VectorizeRaster().process(_make_dataset(array))

    assert (result.geodataframe["relevance_score"] >= 0).all()


def test_vectorize_raster_crs_matches_input():
    """Output GeoDataFrame CRS matches the input RasterDataset CRS."""
    array = np.array([[1.0, 1.0], [1.0, 1.0]], dtype=constants.DEFAULT_DTYPE)
    result = VectorizeRaster().process(_make_dataset(array))

    assert result.geodataframe.crs.to_string() == constants.DEFAULT_CRS


def test_vectorize_raster_invalid_input_raises_error():
    """Non-RasterDataset input raises InvalidStageInputError."""
    with pytest.raises(exceptions.InvalidStageInputError):
        VectorizeRaster().process(None)


def test_vectorize_raster_polygon_follows_pixel_boundaries():
    """Polygonized output geometry matches the pixel boundary of the input cluster.

    Input array (X = data pixel, . = nodata):

        col→  0    1    2    3    4
    row
     0        X    X    X    .    .
     1        X    .    X    .    .
     2        X    X    X    .    .
     3        .    .    .    X    X
     4        .    .    .    X    X

    The top-left cluster (rows 0-2, cols 0-2) has a hole at (row=1, col=1).
    With DEFAULT_TRANSFORM (origin 0,0, pixel size 1, y-scale -1), pixel edges
    map as: x = col, y = -row. So the cluster spans x=[0,3], y=[-3,0].

    The bottom-right cluster (rows 3-4, cols 3-4) is a simple 2x2 rectangle
    spanning x=[3,5], y=[-5,-3].
    """
    array = np.array(
        [
            [1.0, 1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [
                1.0,
                constants.DEFAULT_NODATA,
                1.0,
                constants.DEFAULT_NODATA,
                constants.DEFAULT_NODATA,
            ],
            [1.0, 1.0, 1.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [
                constants.DEFAULT_NODATA,
                constants.DEFAULT_NODATA,
                constants.DEFAULT_NODATA,
                2.0,
                2.0,
            ],
            [
                constants.DEFAULT_NODATA,
                constants.DEFAULT_NODATA,
                constants.DEFAULT_NODATA,
                2.0,
                2.0,
            ],
        ],
        dtype=constants.DEFAULT_DTYPE,
    )
    result = VectorizeRaster().process(_make_dataset(array))

    assert len(result.geodataframe) == 2

    gdf = result.geodataframe.copy()
    gdf = gdf.loc[
        gdf.geometry.apply(lambda g: g.bounds[0]).sort_values().index
    ].reset_index(drop=True)

    top_left = gdf.geometry[0]
    bottom_right = gdf.geometry[1]

    assert top_left.bounds == pytest.approx((0.0, -3.0, 3.0, 0.0))
    assert bottom_right.bounds == pytest.approx((3.0, -5.0, 5.0, -3.0))
    assert len(list(top_left.interiors)) == 1


def test_vectorize_raster_relevance_score_order_reflects_elevation_variance():
    """Cluster with higher elevation variance receives a higher relevance_score.

    Input array (X = varied data, U = uniform data, . = nodata):

        col→  0    1    2    3
    row
     0        U    U    .    .
     1        U    U    .    .
     2        .    .    X    X
     3        .    .    X    X

    Left cluster (rows 0-1, cols 0-1): all values equal 5.0  -> std=0, relevance_score=0.
    Right cluster (rows 2-3, cols 2-3): values 1,2,9,10      -> std>0, relevance_score>0.

    The two clusters are diagonally adjacent at (row=1,col=1) and (row=2,col=2)
    but 4-connectivity labelling does not connect diagonal neighbours, so they
    remain separate labels and receive independent relevance_scores.
    """
    array = np.array(
        [
            [5.0, 5.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [5.0, 5.0, constants.DEFAULT_NODATA, constants.DEFAULT_NODATA],
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 1.0, 2.0],
            [constants.DEFAULT_NODATA, constants.DEFAULT_NODATA, 9.0, 10.0],
        ],
        dtype=constants.DEFAULT_DTYPE,
    )
    result = VectorizeRaster().process(_make_dataset(array))

    assert len(result.geodataframe) == 2

    gdf = result.geodataframe.copy()
    gdf = gdf.loc[
        gdf.geometry.apply(lambda g: g.bounds[0]).sort_values().index
    ].reset_index(drop=True)

    uniform_relevance_score = gdf["relevance_score"][0]
    varied_relevance_score = gdf["relevance_score"][1]

    assert uniform_relevance_score == pytest.approx(0.0)
    assert varied_relevance_score > uniform_relevance_score
