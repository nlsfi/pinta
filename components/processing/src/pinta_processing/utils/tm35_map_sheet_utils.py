# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


"""This file consists of utility functions for working with TM35 maps sheet division sheets.

https://www.maanmittauslaitos.fi/en/maps-and-spatial-data/datasets-and-interfaces/product-descriptions/map-sheet-division
"""  # noqa: E501

import re

import shapely

# positions of lower-left corner by x-y offsets from previous char corner
# origin is at J2 lower-left corner
SHEET_ORIGIN = (-76000, 6474000)

TILE_SIZE = (1000, 1000)

SHEET_CODE_OFFSETS: list[dict[str, tuple[int, int]]] = (
    [
        {char: (0, index * 96000) for index, char in enumerate("JKLMNPQRSTUVWX")},
        {char: (index * 192000, 0) for index, char in enumerate("23456")},
    ]
    + [
        # generate the character sets that have two lines in
        # lower-upper, left-right order
        {
            char: (x_offset * (index // 2), y_offset * (index % 2))
            for index, char in enumerate(chars)
        }
        for chars, x_offset, y_offset in [
            ("1234", 96000, 48000),
            ("1234", 48000, 24000),
            ("1234", 24000, 12000),
            ("ABCDEFGH", 6000, 6000),
            ("1234", 3000, 3000),
        ]
    ]
    + [
        # LAZ files uses naming convention of <map_sheet>_<tile_index>.
        # The map sheet is divided into 9 tiles, lower-upper, left-right order
        {"_": (0, 0)}
    ]
    + [
        {
            char: (TILE_SIZE[0] * (index // 3), TILE_SIZE[1] * (index % 3))
            for index, char in enumerate(map(str, range(1, 10)))
        }
    ]
)

MAP_SHEET_CODE_PATTERN = re.compile(r"[JKLMNPQRSTUVWX][23456][1-4]{3}[A-H][1-4]_[1-9]")


def calculate_sheet_bounds_for_tile(
    map_sheet_code: str,
) -> tuple[int, int, int, int]:
    """Get minx, miny, maxx, maxy of a map sheet code.

    Accepts codes like: <map_sheet>_<tile_index>
    """
    if MAP_SHEET_CODE_PATTERN.fullmatch(map_sheet_code) is None:
        raise ValueError(f"invalid code {map_sheet_code}") from None  # noqa: TRY003

    x, y = SHEET_ORIGIN

    for index, char in enumerate(map_sheet_code):
        x_offset, y_offset = SHEET_CODE_OFFSETS[index][char]
        x += x_offset
        y += y_offset

    return (
        x,
        y,
        x + TILE_SIZE[0],
        y + TILE_SIZE[1],
    )


def calculate_buffered_sheet_geometry(
    map_sheet_code: str,
    buffer_m: float,
) -> shapely.Polygon:
    """Get the buffered map sheet tile geometry.

    Accepts codes like: <map_sheet>_<tile_index>
    """
    return shapely.buffer(calculate_bounding_box_for_tile(map_sheet_code), buffer_m)


def calculate_bounding_box_for_tile(
    map_sheet_code: str,
) -> shapely.Polygon:
    """Get the bounding box of a map sheet tile."""
    return shapely.box(*calculate_sheet_bounds_for_tile(map_sheet_code))
