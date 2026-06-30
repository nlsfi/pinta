# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS raster utilities."""

import logging

import psycopg
import sqlalchemy as sa
import sqlmodel

from pinta_common import Settings
from pinta_db_utils.postgis import utils

DEFAULT_EMPTY_RASTER_ANCHOR = (41248, 7880720)  # upper left
DEFAULT_COVERAGE_TILE_GRID_ANCHOR = (500000, 6570000)
LOGGER = logging.getLogger(__name__)


def add_constraint_regular_blocking(
    session: sqlmodel.Session, schema: str, table_name: str, tile_size_meters: int
) -> None:
    """Add x/y block size constraints to the raster table."""
    if not utils.session_user_owns_table(session, schema, table_name):
        LOGGER.info(
            "Skipping regular blocking constraint creation for %s.%s because "
            "session user is not the table owner",
            schema,
            table_name,
        )
        return

    anchor_x = DEFAULT_COVERAGE_TILE_GRID_ANCHOR[0]
    anchor_y = DEFAULT_COVERAGE_TILE_GRID_ANCHOR[1]

    _add_constraint_from_sql(
        session,
        f"""
            ALTER TABLE "{schema}"."{table_name}"
                ADD CONSTRAINT enforce_coverage_tile_dem_rast CHECK (
                    COALESCE(
                        st_iscoveragetile(null, null, 0, 0),
                        (
                            mod(st_upperleftx(rast)::numeric
                                - {anchor_x}, {tile_size_meters}) = 0
                            AND mod(st_upperlefty(rast)::numeric
                                - {anchor_y}, {tile_size_meters}) = 0
                        )
                    )
                )
        """,
    )
    _add_constraint_from_sql(
        session,
        f"""
            ALTER TABLE {schema}.{table_name}
            ADD CONSTRAINT enforce_spatially_unique_dem_rast_{table_name}
            EXCLUDE USING btree ((rast::geometry) WITH =);
        """,
    )


def add_constraint_extent(
    session: sqlmodel.Session, schema: str, table_name: str
) -> None:
    """Add extent constraints to the raster table."""
    if not utils.session_user_owns_table(session, schema, table_name):
        LOGGER.info(
            "Skipping extent constraint creation for %s.%s because session user "
            "is not the table owner",
            schema,
            table_name,
        )
        return

    session.exec(  # type: ignore[call-overload]
        sa.text(
            "SELECT AddRasterConstraints("
            ":rastschema, :rasttable, :rastcolumn, "
            "FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, "
            "FALSE, FALSE, FALSE, FALSE, FALSE, TRUE"
            ")"
        ).bindparams(
            rastschema=schema,
            rasttable=table_name,
            rastcolumn="rast",
        )
    )


def add_raster_constraints(
    session: sqlmodel.Session, schema: str, table_name: str, pixel_size: int
) -> None:
    """Add all default constraints to the raster table.

    Constraints are generated using empty dummy raster tile.
    """
    if not utils.session_user_owns_table(session, schema, table_name):
        LOGGER.info(
            "Skipping raster constraint creation for %s.%s because session user "
            "is not the table owner",
            schema,
            table_name,
        )
        return

    _make_empty_raster(
        session=session,
        schema=schema,
        table=table_name,
        pixel_size=pixel_size,
    )
    _add_default_raster_constraints(session, schema, table_name)
    session.exec(  # type: ignore[call-overload]
        sa.delete(sa.table(table_name, schema=schema))
    )


def _add_default_raster_constraints(
    session: sqlmodel.Session, schema: str, table_name: str
) -> None:
    # Disabled constraints:
    # - enforce regularly blocking arrangement (generated manually)
    # - extent (generated after data ingestion)
    return session.exec(  # type: ignore[call-overload]
        sa.text("""
        SELECT AddRasterConstraints(
            :rastschema, :rasttable, :rastcolumn,
            TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
            FALSE, TRUE, TRUE, TRUE, TRUE, FALSE
        )
        """).bindparams(
            rastschema=schema,
            rasttable=table_name,
            rastcolumn="rast",
        )
    )


def _make_empty_raster(  # noqa: PLR0913
    session: sqlmodel.Session,
    schema: str,
    table: str,
    pixel_size: int,
    srid: int | None = None,
    nodata: float | None = None,
    upper_left_x: int = DEFAULT_EMPTY_RASTER_ANCHOR[0],
    upper_left_y: int = DEFAULT_EMPTY_RASTER_ANCHOR[1],
) -> None:
    """Insert an empty raster into the specified table."""
    if srid is None:
        srid = int(Settings.DB_SRID)
    if nodata is None:
        nodata = Settings.DB_DEM_NODATA
    session.exec(  # type: ignore[call-overload]
        sa.text(f"""
                   INSERT INTO "{schema}"."{table}" ("rast")
                   SELECT ST_AddBand(
                              ST_MakeEmptyRaster(
                                  :block_size, :block_size, :upper_left_x,
                                  :upper_left_y, :pixel_size,
                                  :negative_pixel_size, 0, 0, :srid
                              ),
                              1,
                              '32BF'::text,
                              0,
                              :nodata
                          )
                   """).bindparams(
            upper_left_x=upper_left_x,
            upper_left_y=upper_left_y,
            pixel_size=pixel_size,
            negative_pixel_size=-pixel_size,
            srid=srid,
            nodata=nodata,
            block_size=Settings.DB_DEFAULT_TILE_SIZE,
        )
    )


def _add_constraint_from_sql(session: sqlmodel.Session, sql: str) -> None:
    """Add constraints to the overview table."""
    try:
        session.exec(sa.text(sql))  # type: ignore[call-overload]
    except sa.exc.ProgrammingError as e:
        if hasattr(e, "orig") and type(e.orig) in (
            psycopg.errors.DuplicateObject,
            psycopg.errors.DuplicateTable,
        ):
            # Constraint already exists, ignore
            session.rollback()
            return
        raise
