# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS raster utilities."""

import enum
from collections import abc

import geoalchemy2
import sqlalchemy as sa
import sqlmodel

OVERLAY_TABLE_NAME = "o_{level}_{table_name}"
DEFAULT_OVERLAY_LEVELS = [2, 8]


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
    table_name: str,
    schema: str,
    staging_tables: int = 0,
    extra_columns: abc.Callable[[], list[sa.Column]] | None = None,
) -> None:
    """Initialize a raster table with optional staging tables.

    Creates a main table and staging tables (when specified) with:
    - rid: serial primary key
    - rast: raster column
    - Additional custom columns (optional)

    The additional columns must be provided as a callable that returns a list of
    SQLAlchemy Column objects as each table needs its own column object instances.

    The rast column storage is set to external for better performance
    with large raster data to avoid unnecessary compression. All tables have
    TOAST tuple target optimized TOAST chunk size. Staging tables are created as
    UNLOGGED with autovacuum disabled for better performance.
    """
    _create_raster_table(
        session,
        table_name,
        schema=schema,
        extra_columns=extra_columns() if extra_columns else None,
    )

    for i in range(staging_tables):
        staging_name = f"{table_name}_p{i}"
        _create_raster_table(
            session,
            staging_name,
            schema=schema,
            extra_columns=extra_columns() if extra_columns else None,
            table_type=TableType.UNLOGGED,
        )

    session.commit()


def initialize_overlay_tables(
    session: sqlmodel.Session,
    table_name: str,
    schema: str,
) -> None:
    """Initialize overlay tables with rid and rast columns.

    Creates a main table and staging tables with:
    - rid: serial primary key
    - rast: raster column
    """
    for level in DEFAULT_OVERLAY_LEVELS:
        overlay_name = OVERLAY_TABLE_NAME.format(level=level, table_name=table_name)
        table = _create_raster_table(
            session,
            overlay_name,
            schema=schema,
        )
        index = sa.Index(
            f"{overlay_name}_rast_idx",
            sa.func.ST_Envelope(table.c.rast),
            postgresql_using="gist",
        )
        index.create(bind=session.connection())


def merge_staging_tables(
    table_name: str,
    schema: str = "public",
    staging_tables: int = 0,
    session: sqlmodel.Session | None = None,
) -> None:
    """Merge data from staging tables into main table, create index.

    Inserts all raster data from staging tables into the main table using UNION ALL,
    then creates a GIST index on the raster envelope and deletes the staging tables.
    """
    if staging_tables == 0 or session is None:
        return

    meta = sa.MetaData()
    union_parts = [
        sa.select(
            sa.Table(
                f"{table_name}_p{i}", meta, sa.Column("rast"), schema=schema
            ).c.rast
        )
        for i in range(staging_tables)
    ]
    union_query = sa.union_all(*union_parts)

    # Insert data from staging tables into main table
    main_table = sa.Table(table_name, meta, sa.Column("rast"), schema=schema)
    insert_query = main_table.insert().from_select(["rast"], union_query)
    session.exec(insert_query)

    index = sa.Index(
        f"{table_name}_rast_idx",
        sa.func.ST_Envelope(main_table.c.rast),
        postgresql_using="gist",
    )
    index.create(bind=session.connection())

    for i in range(staging_tables):
        staging_name = f"{table_name}_p{i}"
        staging_table = sa.Table(staging_name, sa.MetaData(), schema=schema)
        staging_table.drop(bind=session.connection(), checkfirst=True)

    session.commit()


def _set_raster_table_options(
    table_name: str,
    schema: str,
    session: sqlmodel.Session,
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
    table_name: str,
    schema: str = "public",
    extra_columns: list[sa.Column] | None = None,
    table_type: TableType = TableType.TABLE,
) -> sa.Table:
    """Create a raster table."""
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
    table.create(session.connection(), checkfirst=True)

    _set_raster_table_options(table_name, schema, session=session)
    if table_type is TableType.UNLOGGED:
        session.exec(  # type: ignore[call-overload]
            sa.text(f"ALTER TABLE {schema}.{table_name} SET (autovacuum_enabled=false)")
        )
    return table
