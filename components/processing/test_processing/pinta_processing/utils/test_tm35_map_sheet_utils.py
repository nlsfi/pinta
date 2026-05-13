# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest

from pinta_processing.utils import tm35_map_sheet_utils


@pytest.mark.parametrize(
    argnames=("map_sheet_code", "expected_geometry"),
    argvalues=[
        ("P5421C1_5", (603000, 7027000, 604000, 7028000)),
        ("Q5143F4_1", (587000, 7083000, 588000, 7084000)),
        ("T5124H1_1", (542000, 7380000, 543000, 7381000)),
        ("T5124H1_9", (544000, 7382000, 545000, 7383000)),
    ],
)
def test_calculate_map_sheet_geometry(
    map_sheet_code: str, expected_geometry: tuple[int, int, int, int]
):
    assert (
        tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(map_sheet_code)
        == expected_geometry
    )


@pytest.mark.parametrize(
    "map_sheet_code",
    [
        "P5421C1",
        "P5421C1_10",
        "I5421C1_5",
        "P7421C1_5",
        "P5521C1_5",
        "P5421I1_5",
        "P5421C5_5",
        "P5421C1-A",
    ],
)
def test_calculate_map_sheet_geometry_raises_for_invalid_code(map_sheet_code: str):
    with pytest.raises(ValueError, match=f"invalid code {map_sheet_code}"):
        tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(map_sheet_code)


@pytest.mark.parametrize(
    argnames=("map_sheet_code", "buffer_m", "expected_bounds"),
    argvalues=[
        ("P5421C1_5", 50, (602950, 7026950, 604050, 7028050)),
        ("P5421C1_5", 0, (603000, 7027000, 604000, 7028000)),
        ("T5124H1_1", 100, (541900, 7379900, 543100, 7381100)),
    ],
)
def test_calculate_buffered_sheet_geometry(
    map_sheet_code: str,
    buffer_m: float,
    expected_bounds: tuple[int, int, int, int],
):
    geometry = tm35_map_sheet_utils.calculate_buffered_sheet_geometry(
        map_sheet_code, buffer_m
    )

    assert geometry.bounds == expected_bounds


def test_calculate_buffered_sheet_geometry_raises_for_invalid_code():
    with pytest.raises(ValueError, match="invalid code P5421C1"):
        tm35_map_sheet_utils.calculate_buffered_sheet_geometry("P5421C1", 50)
