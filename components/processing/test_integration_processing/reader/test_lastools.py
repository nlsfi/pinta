# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


import numpy as np
import pytest
from pinta_test_utils import pinta_utils

from pinta_processing import core
from pinta_processing.exceptions import LasToolsError
from pinta_processing.reader import lastools
from pinta_processing.utils import tm35_map_sheet_utils

LAZ_DIR = "point_clouds/2025/production_area_1"
CRS = "EPSG:3067"


@pytest.fixture(autouse=True)
def _ensure_lastools_is_available(lastools_in_path: None) -> None:
    pass


def test_blast2dem_reader_produces_raster_from_laz():
    laz_path = pinta_utils.get_test_data_path(f"{LAZ_DIR}/T5124H1_1.laz")

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
    laz_path = pinta_utils.get_test_data_path(f"{LAZ_DIR}/T5124H1_1.laz")

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


def test_blast2dem_reader_with_sensible_parameters():
    target_code = "T5124H1_5"
    laz_dir = pinta_utils.get_test_data_path(LAZ_DIR)
    target_path = laz_dir / f"{target_code}.laz"

    # T5124H1_5 is interior to the H1 sub-sheet, so all 8 neighbors exist
    neighbor_paths = []
    assert len(neighbor_paths) == 8

    bounds = tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(target_code)

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
            "neighbors": [str(p) for p in neighbor_paths],
        },
    )
    dataset = stage.process(None)

    assert isinstance(dataset, core.RasterDataset)
    assert dataset.array.ndim == 2
    assert dataset.array.size > 0
    assert dataset.crs == CRS
