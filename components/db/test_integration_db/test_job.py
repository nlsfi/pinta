# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

import pytest
import sqlalchemy as sa
import sqlmodel

from pinta_db.job_db.models.user import UpdateArea

_PROCESSING_WORKER_ROLE = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]
_WRITER_ROLE = os.environ["DB_JOB_WRITER_ROLE"]


def _edit_as(
    session: sqlmodel.Session,
    role: str,
    area: UpdateArea,
    *,
    dirty: bool | None = None,
    geom: str | None = None,
) -> None:
    """Update the area while acting as ``role``, then reset back to the admin."""
    session.exec(sa.text(f'SET ROLE "{role}"'))  # type: ignore[call-overload]
    if dirty is not None:
        area.dirty = dirty
    if geom is not None:
        area.geom = geom
    session.commit()
    session.exec(sa.text("RESET ROLE"))  # type: ignore[call-overload]
    session.refresh(area)


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


@pytest.mark.parametrize(
    ("initial_dirty", "edit_role", "edit_dirty", "expected_dirty"),
    [
        (False, _WRITER_ROLE, None, True),
        (False, _PROCESSING_WORKER_ROLE, None, False),
        (True, _PROCESSING_WORKER_ROLE, False, False),
        (True, _WRITER_ROLE, False, True),
    ],
    ids=[
        "non-worker-edit-marks-dirty",
        "worker-edit-keeps-clean",
        "worker-clears-dirty",
        "non-worker-cannot-clear-dirty",
    ],
)
def test_set_update_area_dirty_trigger(
    job_db: sqlmodel.Session,
    initial_dirty: bool,
    edit_role: str,
    edit_dirty: bool | None,
    expected_dirty: bool,
):
    area = UpdateArea(geom="Polygon((0 0, 1 0, 1 1, 0 1, 0 0))", dirty=initial_dirty)
    job_db.add(area)
    job_db.commit()
    assert area.dirty is initial_dirty

    _edit_as(
        job_db,
        edit_role,
        area,
        dirty=edit_dirty,
        geom="Polygon((0 0, 2 0, 2 2, 0 2, 0 0))",
    )

    assert area.dirty is expected_dirty
