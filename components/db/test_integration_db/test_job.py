# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import sqlalchemy as sa
import sqlmodel


def _assert_table_exists(
    session: sqlmodel.Session,
    schema: str,
    table_name: str,
) -> None:
    """Assert that a table exists in the database."""
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


def test_job_db(job_db: sqlmodel.Session):
    _assert_table_exists(job_db, "reference", "dem")
    _assert_table_exists(job_db, "reference", "diff_gt_threshold")
    _assert_table_exists(job_db, "reference", "diff_lte_threshold")
    _assert_table_exists(job_db, "reference", "diff_polygon")
    _assert_table_exists(job_db, "reference", "diff_polygon_cluster")
    _assert_table_exists(job_db, "user_data", "update_area")
