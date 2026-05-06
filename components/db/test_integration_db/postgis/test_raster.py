# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
import sqlalchemy as sa
import sqlmodel

from pinta_db.primary_db.schema import Schema
from pinta_db_utils.postgis import raster


def _assert_table_exists(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    table_type: raster.TableType = raster.TableType.TABLE,
) -> None:
    """Assert that a table exists in the database with the correct type."""
    result = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = '{schema}'
                AND table_name = '{table_name}'
            )
            """
        )
    ).first()
    assert result == (True,), f"Table {schema}.{table_name} does not exist"

    # Verify table type (UNLOGGED or regular)
    relkind = "u" if table_type == raster.TableType.UNLOGGED else "p"

    type_result = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT EXISTS (
                SELECT FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = '{table_name}'
                AND n.nspname = '{schema}'
                AND c.relpersistence = '{relkind}'
            )
            """
        )
    ).first()
    assert type_result == (True,), (
        f"Table {schema}.{table_name} is not of type {table_type.value}"
    )


def _assert_staging_tables_does_not_exist(
    session: sqlmodel.Session, schema: str, table_name: str
) -> None:
    """Assert that a any staging table does not exist in the database."""
    staging_result = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_name LIKE '{table_name}_p%'
            """
        )
    ).first()
    assert staging_result == (0,), f"Expected 0 staging tables, got {staging_result[0]}"


def _assert_table_index_count(
    session: sqlmodel.Session, schema: str, table_name: str, expected_count: int = 0
) -> None:
    """Assert that a table has the expected number of indices."""
    indices_result = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = '{schema}'
            AND tablename = '{table_name}'
            """
        )
    ).first()

    assert indices_result == (expected_count,), (
        f"Expected {expected_count} indices on table {schema}.{table_name}, got {indices_result[0]}"
    )


def _assert_table_has_default_columns(
    session: sqlmodel.Session, schema: str, table_name: str
) -> None:
    """Assert that a table has correct columns and types."""
    columns = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table_name}'
            ORDER BY ordinal_position
            """
        )
    ).all()

    assert len(columns) == 2, (
        f"Expected 2 columns on {schema}.{table_name}, got {len(columns)}"
    )
    assert columns[0] == ("rid", "integer"), (
        f"Expected rid column with integer type on {schema}.{table_name}, got {columns[0]}"
    )
    assert columns[1] == ("rast", "USER-DEFINED"), (
        f"Expected rast column with raster type on {schema}.{table_name}, got {columns[1]}"
    )


def _assert_table_columns_match(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
    expected_columns: list[tuple[str, str]],
) -> None:
    """Assert that a table has the expected columns and types."""
    columns = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table_name}'
            ORDER BY ordinal_position
            """
        )
    ).all()

    assert len(columns) == len(expected_columns), (
        f"Expected {len(expected_columns)} columns on {schema}.{table_name}, got {len(columns)}"
    )
    for i, (expected_name, expected_type) in enumerate(expected_columns):
        assert columns[i][0] == expected_name, (
            f"Column {i}: expected {expected_name}, got {columns[i][0]}"
        )
        assert columns[i][1] == expected_type, (
            f"Column {i} ({expected_name}) type: expected {expected_type}, got {columns[i][1]}"
        )


@pytest.mark.parametrize("staging_tables", [0, 3])
def test_initialize_raster_table(
    processing_worker_db: sqlmodel.Session, staging_tables: int
):
    """Test creating a raster table with varying numbers of staging tables."""
    table_name = "test_raster_table"
    schema = Schema.PROCESSING.value
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=staging_tables,
        session=processing_worker_db,
    )
    _assert_table_exists(processing_worker_db, schema, table_name)
    _assert_table_has_default_columns(processing_worker_db, schema, table_name)
    _assert_table_index_count(
        processing_worker_db, schema, table_name, expected_count=1
    )

    if staging_tables == 0:
        # Verify no staging tables exist
        _assert_staging_tables_does_not_exist(processing_worker_db, schema, table_name)
    else:
        for i in range(staging_tables):
            staging_name = f"{table_name}_p{i}"
            _assert_table_exists(
                processing_worker_db,
                schema,
                staging_name,
                table_type=raster.TableType.UNLOGGED,
            )
            _assert_table_has_default_columns(
                processing_worker_db, schema, staging_name
            )
            _assert_table_index_count(
                processing_worker_db, schema, staging_name, expected_count=2
            )


def test_test_merge_staging_tables_with_no_staging_tables_creates_rast_index(
    processing_worker_db: sqlmodel.Session,
):
    table_name = "test_raster_merge_no_staging"
    schema = Schema.PROCESSING.value

    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=0,
        session=processing_worker_db,
    )

    raster.merge_staging_tables(
        table_name=table_name,
        schema=schema,
        staging_tables=0,
        session=processing_worker_db,
    )

    _assert_table_index_count(
        processing_worker_db, schema, table_name, expected_count=2
    )


def test_merge_staging_tables(processing_worker_db: sqlmodel.Session):
    """Test merging staging tables into main raster table."""
    table_name = "test_raster_merge"
    schema = Schema.PROCESSING.value
    staging_tables = 3
    rows_per_staging = 1

    # Initialize table with staging tables
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=staging_tables,
        session=processing_worker_db,
    )

    # Insert dummy raster data into each staging table
    for i in range(staging_tables):
        staging_name = f"{table_name}_p{i}"
        for _ in range(rows_per_staging):
            processing_worker_db.exec(  # type: ignore[call-overload]
                sa.text(f"""
                    INSERT INTO "{schema}"."{staging_name}" ("rast")
                    SELECT ST_AddBand(
                        ST_MakeEmptyRaster(
                            256, 256,
                            41248 + ({i} * 512),   -- shift X
                            7880720,               -- keep Y same
                            2, -2, 0, 0, 3067
                        ),
                        1,
                        '32BF'::text,
                        0,
                        -9999
                    )
                """)
            )
    processing_worker_db.commit()

    # Merge staging tables
    raster.merge_staging_tables(
        table_name=table_name,
        schema=schema,
        staging_tables=staging_tables,
        session=processing_worker_db,
    )

    # Verify main table has correct number of rows
    main_rows = processing_worker_db.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{table_name}")
    ).first()
    expected_rows = staging_tables * rows_per_staging
    assert main_rows == (expected_rows,), (
        f"Expected {expected_rows} rows in main table, got {main_rows[0]}"
    )

    # Verify staging tables are removed
    _assert_staging_tables_does_not_exist(processing_worker_db, schema, table_name)

    # Verify pk and rast index exists on main table
    _assert_table_index_count(
        processing_worker_db, schema, table_name, expected_count=3
    )


def test_initialize_raster_table_with_extra_columns(
    processing_worker_db: sqlmodel.Session,
):
    """Test creating a raster table with extra columns."""
    table_name = "test_raster_extra"
    schema = Schema.PROCESSING.value

    def extra_columns() -> list[sa.Column]:
        return [
            sa.Column("metadata", sa.Text()),
            sa.Column("is_private", sa.Boolean()),
        ]

    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=1,
        session=processing_worker_db,
        extra_columns=extra_columns,
    )

    # Expected columns for both main and staging tables
    expected_columns = [
        ("rid", "integer"),
        ("rast", "USER-DEFINED"),
        ("metadata", "text"),
        ("is_private", "boolean"),
    ]

    # Verify main table has correct columns including extras
    _assert_table_columns_match(
        processing_worker_db, schema, table_name, expected_columns
    )

    # Verify staging table has correct columns including extras
    staging_name = f"{table_name}_p0"
    _assert_table_exists(
        processing_worker_db, schema, staging_name, table_type=raster.TableType.UNLOGGED
    )
    _assert_table_columns_match(
        processing_worker_db, schema, staging_name, expected_columns
    )


@pytest.mark.parametrize("staging_tables", [0, 3])
def test_initialize_raster_table_twice(
    processing_worker_db: sqlmodel.Session, staging_tables: int
):
    """Test calling initialize_raster_table twice."""
    table_name = "test_initialize_table_twice"
    schema = Schema.PROCESSING.value

    # Initialize twice
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=staging_tables,
        session=processing_worker_db,
    )
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        staging_tables=staging_tables,
        session=processing_worker_db,
    )


@pytest.mark.parametrize("staging_tables", [0, 3])
def test_initialize_overview_tables(
    processing_worker_db: sqlmodel.Session, staging_tables: int
):
    """Test creating overview tables."""
    table_name = "test_raster_overview"
    schema = Schema.PROCESSING.value

    raster.initialize_overview_tables(
        table_name=table_name,
        schema=schema,
        session=processing_worker_db,
        staging_tables=staging_tables,
    )

    overview_table_names = [
        raster.OVERVIEW_TABLE_NAME.format(level=level, table_name=table_name)
        for level in raster.DEFAULT_OVERVIEW_LEVELS
    ]

    for overview_table_name in overview_table_names:
        _assert_table_exists(processing_worker_db, schema, overview_table_name)
        _assert_table_has_default_columns(
            processing_worker_db, schema, overview_table_name
        )
        # only pk index
        _assert_table_index_count(
            processing_worker_db, schema, overview_table_name, expected_count=1
        )

        if staging_tables == 0:
            _assert_staging_tables_does_not_exist(
                processing_worker_db, schema, overview_table_name
            )
        else:
            for i in range(staging_tables):
                staging_name = f"{overview_table_name}_p{i}"
                _assert_table_exists(
                    processing_worker_db,
                    schema,
                    staging_name,
                    table_type=raster.TableType.UNLOGGED,
                )
                _assert_table_has_default_columns(
                    processing_worker_db, schema, staging_name
                )
                _assert_table_index_count(
                    processing_worker_db, schema, staging_name, expected_count=1
                )


def test_add_raster_constraints(processing_worker_db: sqlmodel.Session):
    table_name = "dem"
    schema = Schema.PROCESSING.value
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        session=processing_worker_db,
    )

    _assert_table_exists(processing_worker_db, schema, table_name)
    _assert_table_has_default_columns(processing_worker_db, schema, table_name)

    # Assert that constraints are created and registered in raster_columns view
    constraints_result = processing_worker_db.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM raster_columns
            WHERE r_table_schema = '{schema}'
            AND r_table_name = '{table_name}'
            """
        )
    ).first()
    assert constraints_result == (1,), (
        f"Expected raster column {schema}.{table_name} to be registered "
        "in raster_columns view after adding constraints"
    )


def test_register_overview(processing_worker_db: sqlmodel.Session):
    """Test registering overview tables and verifying their constraints."""
    table_name = "dem"
    schema = Schema.PROCESSING.value
    raster.initialize_raster_table(
        table_name=table_name,
        schema=schema,
        session=processing_worker_db,
    )
    raster.initialize_overview_tables(
        table_name=table_name,
        schema=schema,
        session=processing_worker_db,
    )
    raster.finalize_overview_tables(
        session=processing_worker_db,
        schema=schema,
        reference_table_name=table_name,
    )
    # Verify overview tables are registered in raster_overviews catalog
    overviews_result = processing_worker_db.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM raster_overviews
            WHERE r_table_schema = '{schema}'
            AND r_table_name = '{table_name}'
            """
        )
    ).first()
    assert overviews_result == (len(raster.DEFAULT_OVERVIEW_LEVELS),), (
        f"Expected {len(raster.DEFAULT_OVERVIEW_LEVELS)} overview registrations, "
        f"got {overviews_result[0]}"
    )
    # Verify each overview table has an index on rast column
    for level in raster.DEFAULT_OVERVIEW_LEVELS:
        overview_name = raster.OVERVIEW_TABLE_NAME.format(
            level=level, table_name=table_name
        )
        _assert_table_index_count(
            processing_worker_db, schema, overview_name, expected_count=2
        )
