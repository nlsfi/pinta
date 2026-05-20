# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

import numpy as np
import pytest
import rasterio
from pinta_db_utils.postgis import raster
from pinta_test_utils import pinta_utils

from pinta_processing import core, reader, writer

if typing.TYPE_CHECKING:
    from sqlmodel import Session


def test_postgis_reader_clips_raster_from_database(
    processing_worker_session: "Session",
) -> None:
    file_path = _write_dem_to_postgis(processing_worker_session)

    with rasterio.open(str(file_path)) as src:
        expected_array = src.read(1)
        expected_bounds = src.bounds
        expected_crs = src.crs.to_string()
        expected_transform = src.transform
        expected_nodata = src.nodata

    wkt = _bounds_to_wkt(
        expected_bounds.left,
        expected_bounds.bottom,
        expected_bounds.right,
        expected_bounds.top,
    )
    result = reader.PostgisReader(
        "processing", "dem", processing_worker_session, wkt
    ).process(None)

    assert isinstance(result, core.RasterDataset)
    assert result.array.shape == expected_array.shape
    assert np.array_equal(result.array, expected_array)
    assert result.crs == expected_crs
    assert result.transform == expected_transform
    assert result.nodata == expected_nodata


def test_postgis_reader_clip_partly_nodata_wkt(
    processing_worker_session: "Session",
) -> None:
    file_path = _write_dem_to_postgis(processing_worker_session)

    with rasterio.open(str(file_path)) as src:
        expected_array = src.read(1)[:, 386:389]
        nodata = src.nodata
        transform = src.transform
        left, top = transform * (386, 0)
        right, bottom = transform * (389, src.height)

    wkt = _bounds_to_wkt(left, bottom, right, top)
    result = reader.PostgisReader(
        "processing", "dem", processing_worker_session, wkt
    ).process(None)

    assert result.array.shape == expected_array.shape
    assert np.array_equal(result.array, expected_array)
    assert np.any(result.array == nodata)
    assert np.any(result.array != nodata)
    assert result.nodata == nodata


def test_postgis_reader_clip_all_nodata_wkt(
    processing_worker_session: "Session",
) -> None:
    file_path = _write_dem_to_postgis(processing_worker_session)

    with rasterio.open(str(file_path)) as src:
        expected_array = src.read(1)[:, 387:388]
        nodata = src.nodata
        transform = src.transform
        left, top = transform * (387, 0)
        right, bottom = transform * (388, src.height)

    wkt = _bounds_to_wkt(left, bottom, right, top)
    result = reader.PostgisReader(
        "processing", "dem", processing_worker_session, wkt
    ).process(None)

    assert result.array.shape == expected_array.shape
    assert np.array_equal(result.array, expected_array)
    assert np.all(result.array == nodata)
    assert result.nodata == nodata


def test_postgis_reader_raises_when_wkt_has_no_raster_data(
    processing_worker_session: "Session",
) -> None:
    _write_dem_to_postgis(processing_worker_session)

    wkt = _bounds_to_wkt(0.0, 0.0, 10.0, 10.0)
    stage = reader.PostgisReader("processing", "dem", processing_worker_session, wkt)

    with pytest.raises(ValueError, match=r"No raster data found in processing\.dem"):
        stage.process(None)


def _write_dem_to_postgis(processing_worker_session: "Session") -> str:
    raster.initialize_raster_table(processing_worker_session, "processing", "dem")
    file_path = pinta_utils.get_test_data_path("processing/dem.tif")

    pipeline = reader.RasterioReader(str(file_path)) | writer.PostgisWriter(
        "processing", "dem", processing_worker_session
    )
    pipeline.execute()

    return str(file_path)


def _bounds_to_wkt(left: float, bottom: float, right: float, top: float) -> str:
    return (
        "POLYGON(("
        f"{left} {bottom}, "
        f"{right} {bottom}, "
        f"{right} {top}, "
        f"{left} {top}, "
        f"{left} {bottom}"
        "))"
    )
