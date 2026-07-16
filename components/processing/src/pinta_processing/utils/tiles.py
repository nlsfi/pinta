# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Global raster tile grid helpers.

Every raster tile written to PostGIS is snapped to the global grid anchored at
DEFAULT_COVERAGE_TILE_GRID_ANCHOR with tiles of tile_size pixels a side. These
helpers enumerate that grid and probe tables for existing tiles so callers can
reason about which tile rows a raster write will touch without generating the
rasters themselves.
"""

import enum
import math

import shapely
import sqlalchemy as sa
import sqlmodel
from pinta_common import Settings
from pinta_db_utils.postgis import constraints
from shapely.geometry.base import BaseGeometry

GRID_ORIGIN_X, GRID_ORIGIN_Y = constraints.DEFAULT_COVERAGE_TILE_GRID_ANCHOR


def tile_envelopes(
    geometry: BaseGeometry,
    pixel_size: float,
    tile_size: int,
) -> list[shapely.Polygon]:
    """Return the grid-aligned tile envelopes the geometry overlaps.

    Tiles that only touch the geometry boundary are excluded: their pixels
    cannot fall inside the geometry, so a write clipped to it never fills them.
    """
    tile_span = tile_size * pixel_size
    xmin, ymin, xmax, ymax = geometry.bounds

    grid_xmin = (
        GRID_ORIGIN_X + math.floor((xmin - GRID_ORIGIN_X) / tile_span) * tile_span
    )
    grid_ymin = (
        GRID_ORIGIN_Y + math.floor((ymin - GRID_ORIGIN_Y) / tile_span) * tile_span
    )

    envelopes = []
    y = grid_ymin
    while y < ymax:
        x = grid_xmin
        while x < xmax:
            envelope = shapely.box(x, y, x + tile_span, y + tile_span)
            if envelope.intersects(geometry) and not envelope.touches(geometry):
                envelopes.append(envelope)
            x += tile_span
        y += tile_span
    return envelopes


class TileExistsMode(enum.Enum):
    """How tile_exists decides that a tile counts as existing."""

    # A row with exactly the probed envelope exists.
    EXISTS = enum.auto()
    # The row exists and every pixel holds data. A tile initialized at a
    # coverage boundary exists but carries nodata outside the covered part,
    # so existence alone does not prove the tile is a full background.
    ALL_PIXELS_HAVE_DATA = enum.auto()


def tile_exists(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    envelope: shapely.Polygon,
    mode: TileExistsMode = TileExistsMode.EXISTS,
) -> bool:
    """Return True when the raster table has a tile with exactly this envelope.

    Tiles are rectangles, so the bounding box equality operator ~= compares
    the envelopes exactly (geometry = would compare vertex ordering, which
    differs between ST_Envelope output and the probe polygon). The
    ST_Intersects prefilter narrows the scan through the spatial index before
    the exact comparison.
    """
    table = sa.Table(table_name, sa.MetaData(), sa.Column("rast"), schema=schema)
    probe = sa.func.ST_GeomFromText(sa.bindparam("wkt"), int(Settings.DB_SRID))
    conditions = [
        sa.func.ST_Intersects(table.c.rast, probe),
        sa.func.ST_Envelope(table.c.rast).op("~=")(probe),
    ]
    if mode is TileExistsMode.ALL_PIXELS_HAVE_DATA:
        # Every pixel holds data: the count of non-nodata pixels is the size.
        conditions.append(
            sa.func.ST_Count(table.c.rast, 1, True)  # noqa: FBT003
            == sa.func.ST_Width(table.c.rast) * sa.func.ST_Height(table.c.rast)
        )
    query = sa.select(sa.exists().where(sa.and_(*conditions)))
    row = session.exec(query, params={"wkt": envelope.wkt}).one()
    return bool(row[0])
