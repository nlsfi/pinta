# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


import typing

import numpy as np
import pytest
from pinta_test_utils import pinta_utils

from pinta_processing import core
from pinta_processing.exceptions import LasToolsError
from pinta_processing.reader import lastools
from pinta_processing.scripts import find_intersecting_tiles, process_metadata
from pinta_processing.utils import tm35_map_sheet_utils

if typing.TYPE_CHECKING:
    from sqlmodel import Session

LAZ_DIR = "point_clouds/2025/production_area_1"
CRS = "EPSG:3067"
BUFFER_M = 50.0


@pytest.fixture(autouse=True)
def _ensure_lastools_is_available(lastools_in_path: None) -> None:
    pass


@pytest.fixture(autouse=True)
def set_blast2dem_executable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(lastools.Blast2DemReader, "executable", "las2dem_new64")


@pytest.fixture
def add_tiles_to_db(session: "Session") -> None:
    laz_dir = pinta_utils.get_test_data_path(LAZ_DIR)

    # Store every tile in the folder so the spatial query has something to find.
    tiles = process_metadata.create_point_cloud_tiles_from_folder(laz_dir)
    production_area = process_metadata.find_production_area(laz_dir, session)
    process_metadata.add_tiles_to_production_area(production_area, tiles, session)
    session.commit()


def test_blast2dem_reader_produces_raster_from_laz():
    laz_path = pinta_utils.get_test_data_path(f"{LAZ_DIR}/N5122B4_1.laz")

    stage = lastools.Blast2DemReader(
        input_path=laz_path,
        step=1,
        crs=CRS,
        keep_class=[2],
    )
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.ndim == 2
    assert dataset.array.size > 0
    assert dataset.array.dtype.kind == "f"
    assert dataset.crs == CRS
    assert dataset.transform is not None


def test_blast2dem_reader_raises_on_invalid_input():
    missing_path = pinta_utils.get_test_data_path(
        f"{LAZ_DIR}/does_not_exist.laz", check_if_exists=False
    )

    stage = lastools.Blast2DemReader(
        input_path=missing_path,
        step=1,
        crs=CRS,
        keep_class=[2],
    )
    with pytest.raises(LasToolsError):
        stage.process(None)


def test_blast2dem_reader_output_overlaps_input_bounds():
    laz_path = pinta_utils.get_test_data_path(f"{LAZ_DIR}/N5122B4_1.laz")

    stage = lastools.Blast2DemReader(
        input_path=laz_path,
        step=1,
        crs=CRS,
        keep_class=[2],
    )
    dataset = stage.process(None)

    # Transform places the raster somewhere on the TM35FIN grid; the origin
    # must be within reasonable Finland coordinates (sanity check).
    origin_x, origin_y = dataset.transform.c, dataset.transform.f
    assert 0 < origin_x < 1_000_000
    assert 6_000_000 < origin_y < 8_000_000
    # The raster contains at least some non-nodata pixels.
    if dataset.nodata is not None:
        assert np.any(dataset.array != dataset.nodata)


@pytest.mark.usefixtures("add_tiles_to_db")
def test_blast2dem_reader_with_sensible_parameters(session: "Session"):
    laz_dir = pinta_utils.get_test_data_path(LAZ_DIR)

    target_code = "N5122B4_5"
    target_path = laz_dir / f"{target_code}.laz"

    bounds = tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(target_code)
    neighbor_paths = find_intersecting_tiles.find_neighboring_tm35_laz_files(
        target_path, BUFFER_M, session
    )

    # N5122B4_5 is interior to the H1 sub-sheet, so all 8 neighbors exist
    assert len(neighbor_paths) == 8

    stage = lastools.Blast2DemReader(
        input_path=target_path,
        step=2,
        crs=CRS,
        keep_class=[2],
        extra_lastools_params={
            "buffered": 300,
            "kill": 300,
            "ll": [bounds[0], bounds[1]],
            "ncols": 1000,
            "nrows": 1000,
            "neighbors": [str(neighbor) for neighbor in neighbor_paths],
        },
    )
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.ndim == 2
    assert dataset.array.size > 0
    assert dataset.crs == CRS
