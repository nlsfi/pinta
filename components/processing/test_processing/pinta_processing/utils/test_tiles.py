# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from unittest.mock import MagicMock

import numpy as np
import shapely
from pinta_db_utils.postgis import constraints
from rasterio.transform import Affine

from pinta_processing import core
from pinta_processing.utils import tiles
from pinta_processing.writer import RasterPostgisWriter

# One grid tile: 256 pixels of 2 m, anchored at the global origin.
PIXEL_SIZE = 2.0
TILE_SIZE = 256
TILE_SPAN = TILE_SIZE * PIXEL_SIZE


def test_grid_origin_is_the_shared_coverage_tile_anchor() -> None:
    origin = (tiles.GRID_ORIGIN_X, tiles.GRID_ORIGIN_Y)
    assert origin == constraints.DEFAULT_COVERAGE_TILE_GRID_ANCHOR


def test_geometry_inside_one_tile_returns_its_envelope() -> None:
    geometry = shapely.box(
        tiles.GRID_ORIGIN_X + 100,
        tiles.GRID_ORIGIN_Y + 100,
        tiles.GRID_ORIGIN_X + 200,
        tiles.GRID_ORIGIN_Y + 200,
    )

    envelopes = tiles.tile_envelopes(geometry, PIXEL_SIZE, TILE_SIZE)

    assert len(envelopes) == 1
    assert envelopes[0].bounds == (
        tiles.GRID_ORIGIN_X,
        tiles.GRID_ORIGIN_Y,
        tiles.GRID_ORIGIN_X + TILE_SPAN,
        tiles.GRID_ORIGIN_Y + TILE_SPAN,
    )


def test_geometry_straddling_grid_lines_returns_every_overlapped_tile() -> None:
    # Centered on a grid corner, so the geometry overlaps four tiles.
    geometry = shapely.box(
        tiles.GRID_ORIGIN_X - 10,
        tiles.GRID_ORIGIN_Y - 10,
        tiles.GRID_ORIGIN_X + 10,
        tiles.GRID_ORIGIN_Y + 10,
    )

    envelopes = tiles.tile_envelopes(geometry, PIXEL_SIZE, TILE_SIZE)

    assert len(envelopes) == 4
    for envelope in envelopes:
        xmin, ymin, xmax, ymax = envelope.bounds
        assert (xmin - tiles.GRID_ORIGIN_X) % TILE_SPAN == 0
        assert (ymin - tiles.GRID_ORIGIN_Y) % TILE_SPAN == 0
        assert xmax - xmin == TILE_SPAN
        assert ymax - ymin == TILE_SPAN


def test_tile_only_touched_by_the_geometry_boundary_is_excluded() -> None:
    # The east edge lies exactly on a grid line: the eastern tile is only
    # touched and can never receive a pixel.
    geometry = shapely.box(
        tiles.GRID_ORIGIN_X + 100,
        tiles.GRID_ORIGIN_Y + 100,
        tiles.GRID_ORIGIN_X + TILE_SPAN,
        tiles.GRID_ORIGIN_Y + 200,
    )

    envelopes = tiles.tile_envelopes(geometry, PIXEL_SIZE, TILE_SIZE)

    assert len(envelopes) == 1
    assert envelopes[0].bounds[0] == tiles.GRID_ORIGIN_X


def test_pixel_size_scales_the_tile_span() -> None:
    geometry = shapely.box(
        tiles.GRID_ORIGIN_X + 100,
        tiles.GRID_ORIGIN_Y + 100,
        tiles.GRID_ORIGIN_X + 200,
        tiles.GRID_ORIGIN_Y + 200,
    )
    overview_factor = 8

    envelopes = tiles.tile_envelopes(geometry, PIXEL_SIZE * overview_factor, TILE_SIZE)

    assert len(envelopes) == 1
    xmin, ymin, xmax, ymax = envelopes[0].bounds
    assert xmax - xmin == TILE_SPAN * overview_factor
    assert ymax - ymin == TILE_SPAN * overview_factor


def test_tile_exists_reads_the_exists_flag() -> None:
    session = MagicMock()
    envelope = shapely.box(0, 0, 10, 10)

    session.exec.return_value.one.return_value = (True,)
    assert tiles.tile_exists(session, "dem", "dem", envelope) is True

    session.exec.return_value.one.return_value = (False,)
    assert tiles.tile_exists(session, "dem", "dem", envelope) is False


def test_tile_exists_probes_with_the_exact_envelope() -> None:
    session = MagicMock()
    session.exec.return_value.one.return_value = (True,)
    envelope = shapely.box(0, 0, 10, 10)

    tiles.tile_exists(session, "dem", "dem", envelope)

    # The whole envelope is the probe: a partially overlapping tile must not
    # count as coverage, only a tile with exactly this envelope. The bbox
    # equality operator ~= makes the comparison exact for the rectangle tiles.
    assert session.exec.call_args.kwargs["params"] == {"wkt": envelope.wkt}
    query = str(session.exec.call_args.args[0])
    assert "ST_Envelope" in query
    assert "~=" in query
    assert "ST_Intersects" in query
    # Existence alone does not care about nodata pixels.
    assert "ST_Count" not in query


def test_tile_exists_all_pixels_mode_reads_the_exists_flag() -> None:
    session = MagicMock()
    envelope = shapely.box(0, 0, 10, 10)
    mode = tiles.TileExistsMode.ALL_PIXELS_HAVE_DATA

    session.exec.return_value.one.return_value = (True,)
    assert tiles.tile_exists(session, "dem", "dem", envelope, mode=mode) is True

    session.exec.return_value.one.return_value = (False,)
    assert tiles.tile_exists(session, "dem", "dem", envelope, mode=mode) is False


def test_tile_exists_all_pixels_mode_requires_every_pixel_to_hold_data() -> None:
    session = MagicMock()
    session.exec.return_value.one.return_value = (True,)
    envelope = shapely.box(0, 0, 10, 10)

    tiles.tile_exists(
        session, "dem", "dem", envelope, mode=tiles.TileExistsMode.ALL_PIXELS_HAVE_DATA
    )

    # On top of the exact envelope match, the non-nodata pixel count must
    # equal the tile size: a partially filled boundary tile does not count.
    query = str(session.exec.call_args.args[0])
    assert "~=" in query
    assert "ST_Count" in query
    assert "ST_Width" in query
    assert "ST_Height" in query


def test_envelopes_match_the_tiles_the_postgis_writer_generates() -> None:
    # A raster with valid data everywhere, deliberately not grid aligned and
    # spanning grid lines in both axes.
    transform = Affine(
        PIXEL_SIZE,
        0.0,
        tiles.GRID_ORIGIN_X + 100,
        0.0,
        -PIXEL_SIZE,
        tiles.GRID_ORIGIN_Y + 700,
    )
    dataset = core.RasterDataset(
        array=np.ones((300, 300), dtype=np.float32),
        transform=transform,
        crs="EPSG:3067",
        nodata=-9999.0,
    )
    writer = RasterPostgisWriter("foo", "bar", None, tile_size=TILE_SIZE)  # type: ignore[arg-type]

    tile_bounds = {
        (
            tile.transform.c,
            tile.transform.f - TILE_SPAN,
            tile.transform.c + TILE_SPAN,
            tile.transform.f,
        )
        for tile in writer._generate_tiles(dataset)
    }
    envelope_bounds = {
        envelope.bounds
        for envelope in tiles.tile_envelopes(
            shapely.box(*dataset.bounds), PIXEL_SIZE, TILE_SIZE
        )
    }

    assert envelope_bounds == tile_bounds
