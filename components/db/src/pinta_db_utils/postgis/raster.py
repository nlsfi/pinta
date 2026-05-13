# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS raster utilities."""

import enum
import logging
from collections import abc

import geoalchemy2
import sqlalchemy as sa
import sqlmodel

from pinta_common import env
from pinta_db_utils.postgis import constraints, utils

OVERVIEW_TABLE_NAME = "o_{level}_{table_name}"
DEFAULT_OVERVIEW_LEVELS = [2, 8, 128]

LOGGER = logging.getLogger(__name__)


class TableType(enum.Enum):
    """Defines if the table is a regular table or an UNLOGGED table."""

    TABLE = "TABLE"
    UNLOGGED = "UNLOGGED TABLE"


def get_default_columns() -> list[sa.Column]:
    """Get the default columns for raster tables."""
    return [
        sa.Column("rid", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("rast", geoalchemy2.Raster(spatial_index=False)),
    ]


def initialize_raster_table(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    staging_tables: int = 1,
    extra_columns: abc.Callable[[], list[sa.Column]] | None = None,
) -> None:
    """Initialize a raster table with optional staging tables.

    Creates a main table and staging tables (when specified) with:
    - rid: serial primary key
    - rast: raster column
    - Additional custom columns (optional)
    - Basic raster constraints

    The additional columns must be provided as a callable that returns a list of
    SQLAlchemy Column objects as each table needs its own column object instances.

    The rast column storage is set to external for better performance
    with large raster data to avoid unnecessary compression. All tables have
    TOAST tuple target optimized TOAST chunk size. Staging tables are created as
    UNLOGGED with autovacuum disabled for better performance.
    """
    table_created = _create_raster_table(
        session,
        schema,
        table_name,
        extra_columns=extra_columns() if extra_columns else None,
    )
    if table_created:
        constraints.add_raster_constraints(
            session, schema, table_name, pixel_size=env.DEM_PIXEL_SIZE
        )

    for i in range(staging_tables):
        staging_name = f"{table_name}_p{i}"
        _create_raster_table(
            session,
            schema,
            staging_name,
            extra_columns=extra_columns() if extra_columns else None,
            table_type=TableType.UNLOGGED,
        )
        constraints.add_raster_constraints(
            session, schema, staging_name, pixel_size=env.DEM_PIXEL_SIZE
        )
        _create_raster_index(session, schema, staging_name)

    session.commit()


def initialize_overview_tables(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    staging_tables: int = 1,
) -> None:
    """Initialize, register and index overview tables with optional staging tables.

    Creates a main table and staging tables with:
    - rid: serial primary key
    - rast: raster column

    The main overview tables are also registered against the reference raster
    table with PostGIS overview constraints and receive raster envelope indexes.
    """
    for level in DEFAULT_OVERVIEW_LEVELS:
        overview_name = OVERVIEW_TABLE_NAME.format(level=level, table_name=table_name)
        table_created = _create_raster_table(
            session,
            schema,
            overview_name,
        )
        if table_created:
            constraints.add_raster_constraints(
                session, schema, overview_name, pixel_size=env.DEM_PIXEL_SIZE * level
            )

        for i in range(staging_tables):
            staging_name = f"{overview_name}_p{i}"
            _create_raster_table(
                session,
                schema,
                staging_name,
                table_type=TableType.UNLOGGED,
            )
            constraints.add_raster_constraints(
                session, schema, staging_name, pixel_size=env.DEM_PIXEL_SIZE * level
            )

        _register_overview_table(session, schema, table_name, overview_name, level)
        _create_raster_index(session, schema, overview_name)
        session.commit()


def merge_staging_tables(
    schema: str,
    table_name: str,
    staging_tables: int = 1,
    session: sqlmodel.Session | None = None,
    overview_level: int = 1,
) -> None:
    """Merge data from staging tables into main table, create raster indexes.

    Inserts all raster data from staging tables into the main table using a CTE-based
    merge that handles duplicate geometries by merging overlapping rasters, then
    creates a GIST index on the raster envelope and deletes the staging tables.

    Finally add extent and coverage constraints.
    """
    if session is None:
        return
    if staging_tables == 0:
        # No staging tables to merge, just create raster index on main table
        _create_raster_index(session, schema, table_name)
        return

    # Build UNION ALL of all staging tables using SQLAlchemy
    staging_selects = [
        sa.select(
            sa.Table(
                f"{table_name}_p{i}",
                sa.MetaData(),
                sa.Column("rast", geoalchemy2.Raster()),
                schema=schema,
            ).c.rast
        )
        for i in range(staging_tables)
    ]
    staging_union = sa.union_all(*staging_selects).alias("staging_data")

    # Build CTEs for merge logic
    all_tiles = sa.select(
        staging_union.c.rast,
        sa.func.ST_SnapToGrid(sa.func.ST_Envelope(staging_union.c.rast), 0).label(
            "geom"
        ),
    ).cte("all_tiles")

    duplicate_tile_geoms = (
        sa.select(all_tiles.c.geom)
        .group_by(all_tiles.c.geom)
        .having(sa.func.count(all_tiles.c.geom) > 1)
        .cte("duplicate_tile_geoms")
    )

    duplicate_tiles = (
        sa.select(all_tiles)
        .join(duplicate_tile_geoms, all_tiles.c.geom == duplicate_tile_geoms.c.geom)
        .cte("duplicate_tiles")
    )

    unique_tiles = (
        sa.select(all_tiles)
        .outerjoin(
            duplicate_tile_geoms, all_tiles.c.geom == duplicate_tile_geoms.c.geom
        )
        .where(duplicate_tile_geoms.c.geom.is_(None))
        .cte("unique_tiles")
    )

    merged_duplicate_tiles = (
        sa.select(
            duplicate_tiles.c.geom,
            sa.func.ST_Union(duplicate_tiles.c.rast).label("rast"),
        )
        .group_by(duplicate_tiles.c.geom)
        .cte("merged_duplicate_tiles")
    )

    tiles_to_main_table = sa.union_all(
        sa.select(merged_duplicate_tiles.c.rast),
        sa.select(unique_tiles.c.rast),
    ).cte("tiles_to_main_table")

    # Build and execute INSERT statement
    main_table = sa.Table(
        table_name,
        sa.MetaData(),
        sa.Column("rast", geoalchemy2.Raster()),
        schema=schema,
    )

    insert_statement = sa.insert(main_table).from_select(
        [main_table.c.rast],
        sa.select(tiles_to_main_table.c.rast).select_from(tiles_to_main_table),
    )

    session.exec(insert_statement)  # type: ignore[call-overload]
    session.commit()

    _create_raster_index(session, schema, table_name)
    constraints.add_constraint_extent(session, schema, table_name)
    constraints.add_constraint_regular_blocking(
        session,
        schema,
        table_name,
        tile_size_meters=env.DEFAULT_TILE_SIZE * env.DEM_PIXEL_SIZE * overview_level,
    )

    for i in range(staging_tables):
        staging_name = f"{table_name}_p{i}"
        staging_table = sa.Table(staging_name, sa.MetaData(), schema=schema)
        staging_table.drop(bind=session.connection(), checkfirst=True)

    session.commit()


def _register_overview_table(
    session: sqlmodel.Session,
    schema: str,
    reference_table_name: str,
    overview_name: str,
    level: int,
) -> None:
    if not utils.session_user_owns_table(session, schema, overview_name):
        LOGGER.info(
            "Skipping overview registration for %s.%s because session user is "
            "not the table owner",
            schema,
            overview_name,
        )
        return

    session.exec(  # type: ignore[call-overload]
        sa.text(
            "SELECT AddOverviewConstraints("
            ":ovschema, :ovtable, :ovcolumn, :refschema, "
            ":reftable, :refcolumn, :ovfactor)"
        ).bindparams(
            ovschema=schema,
            ovtable=overview_name,
            ovcolumn="rast",
            refschema=schema,
            reftable=reference_table_name,
            refcolumn="rast",
            ovfactor=level,
        )
    )


def _set_raster_table_options(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
) -> None:
    """Set raster table options including EXTERNAL storage and TOAST optimization."""
    session.exec(  # type: ignore[call-overload]
        sa.text(
            f"ALTER TABLE {schema}.{table_name} ALTER COLUMN rast SET STORAGE EXTERNAL"
        )
    )
    session.exec(  # type: ignore[call-overload]
        sa.text(f"ALTER TABLE {schema}.{table_name} SET (toast_tuple_target=8160)")
    )


def _create_raster_table(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    extra_columns: list[sa.Column] | None = None,
    table_type: TableType = TableType.TABLE,
) -> bool:
    """Create a raster table.

    Returns True if table was created, False if it already existed.
    """
    LOGGER.info("Creating raster table %s.%s", schema, table_name)
    # Check if table already exists
    inspector = sa.inspect(session.connection())
    if table_name in inspector.get_table_names(schema=schema):
        return False

    cols = get_default_columns()
    if extra_columns:
        cols.extend(extra_columns)

    prefixes = ["UNLOGGED"] if table_type is TableType.UNLOGGED else []
    table = sa.Table(
        table_name,
        sa.MetaData(),
        *cols,
        schema=schema,
        prefixes=prefixes,
    )
    table.create(session.connection())

    _set_raster_table_options(session, schema, table_name)
    if table_type is TableType.UNLOGGED:
        session.exec(  # type: ignore[call-overload]
            sa.text(f"ALTER TABLE {schema}.{table_name} SET (autovacuum_enabled=false)")
        )

    return True


def _create_raster_index(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
) -> None:
    """Create a GIST index on the raster envelope."""
    if not utils.session_user_owns_table(session, schema, table_name):
        LOGGER.info(
            "Skipping raster index creation for %s.%s because session user is "
            "not the table owner",
            schema,
            table_name,
        )
        return

    index = sa.Index(
        f"{table_name}_rast_idx",
        sa.func.ST_Envelope(
            sa.Table(table_name, sa.MetaData(), sa.Column("rast"), schema=schema).c.rast
        ),
        postgresql_using="gist",
    )
    index.create(bind=session.connection(), checkfirst=True)
