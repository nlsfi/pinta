# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from pathlib import Path

from pinta_db.primary_db.models.management import PointCloudTile, ProductionArea

from pinta_processing.scripts import find_intersecting_tiles

if typing.TYPE_CHECKING:
    from sqlmodel import Session

# Map sheet T5124H1_1 bounds (542000, 7380000, 543000, 7381000).
MAP_SHEET_CODE = "T5124H1_1"
BUFFER_M = 50.0


def _add_tile(
    session: "Session",
    production_area: ProductionArea,
    file_path: str,
    geom: str,
) -> PointCloudTile:
    tile = PointCloudTile(
        geom=geom, file_path=file_path, production_area=production_area
    )
    session.add(tile)
    return tile


def test_find_neighboring_tm35_laz_files(session: "Session"):
    production_area = ProductionArea(
        name="area 1",
        geom="MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))",
    )
    session.add(production_area)

    _add_tile(
        session,
        production_area,
        "inside.laz",
        "Polygon((542100 7380100, 542900 7380100, "
        "542900 7380900, 542100 7380900, 542100 7380100))",
    )
    _add_tile(
        session,
        production_area,
        "edge_overlap.laz",
        "Polygon((542900 7380900, 543200 7380900, "
        "543200 7381200, 542900 7381200, 542900 7380900))",
    )
    # Outside the 1 km sheet but within the default 50 m buffer.
    _add_tile(
        session,
        production_area,
        "in_buffer.laz",
        "Polygon((543010 7380400, 543040 7380400, "
        "543040 7380600, 543010 7380600, 543010 7380400))",
    )
    _add_tile(
        session,
        production_area,
        "far_away.laz",
        "Polygon((600000 7400000, 600100 7400000, "
        "600100 7400100, 600000 7400100, 600000 7400000))",
    )
    # The LAZ file itself: must be excluded even though its geometry
    # intersects the buffered search area.
    target_path = Path(f"/data/{MAP_SHEET_CODE}.laz")
    _add_tile(
        session,
        production_area,
        str(target_path),
        "Polygon((542000 7380000, 543000 7380000, "
        "543000 7381000, 542000 7381000, 542000 7380000))",
    )
    session.commit()

    paths = find_intersecting_tiles.find_neighboring_tm35_laz_files(
        target_path, BUFFER_M, session
    )

    assert set(paths) == {
        Path("inside.laz"),
        Path("edge_overlap.laz"),
        Path("in_buffer.laz"),
    }


def test_find_neighboring_tm35_laz_files_without_buffer(session: "Session"):
    production_area = ProductionArea(
        name="area 1",
        geom="MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))",
    )
    session.add(production_area)

    _add_tile(
        session,
        production_area,
        "inside.laz",
        "Polygon((542100 7380100, 542900 7380100, "
        "542900 7380900, 542100 7380900, 542100 7380100))",
    )
    # Within the 50 m buffer but outside the bare sheet bounds.
    _add_tile(
        session,
        production_area,
        "in_buffer.laz",
        "Polygon((543010 7380400, 543040 7380400, "
        "543040 7380600, 543010 7380600, 543010 7380400))",
    )
    session.commit()

    paths = find_intersecting_tiles.find_neighboring_tm35_laz_files(
        Path(f"/data/{MAP_SHEET_CODE}.laz"), 0, session
    )

    assert set(paths) == {Path("inside.laz")}
