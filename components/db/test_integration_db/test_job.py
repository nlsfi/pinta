# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import datetime
import os

import pytest
import sqlalchemy as sa
import sqlmodel
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape

from pinta_db.job_db.models.user import UpdateArea, UpdateAreaRestore

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
    _assert_table_exists(job_db, "reference", "update_area_suggestion")
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


def _add_registered_update_area(session: sqlmodel.Session) -> UpdateArea:
    """Insert an update area and stamp it registered."""
    area = UpdateArea(geom="Polygon((0 0, 1 0, 1 1, 0 1, 0 0))", dirty=False)
    session.add(area)
    session.commit()

    # Stamping registered_at on an unregistered row is the one allowed change.
    area.registered_at = datetime.datetime(2026, 8, 31, 12, 0)
    session.commit()
    session.refresh(area)
    return area


@pytest.mark.parametrize(
    "edit_role",
    [None, _WRITER_ROLE, _PROCESSING_WORKER_ROLE],
    ids=["admin", "writer", "worker"],
)
def test_registered_update_area_cannot_be_updated(
    job_db: sqlmodel.Session,
    edit_role: str | None,
):
    area = _add_registered_update_area(job_db)

    if edit_role is not None:
        job_db.exec(sa.text(f'SET ROLE "{edit_role}"'))  # type: ignore[call-overload]
    area.geom = "Polygon((0 0, 2 0, 2 2, 0 2, 0 0))"
    with pytest.raises(sa.exc.ProgrammingError, match="can no longer be modified"):
        job_db.commit()
    job_db.rollback()
    job_db.exec(sa.text("RESET ROLE"))  # type: ignore[call-overload]


def test_registered_update_area_cannot_be_deleted(job_db: sqlmodel.Session):
    area = _add_registered_update_area(job_db)

    job_db.delete(area)
    with pytest.raises(sa.exc.ProgrammingError, match="can no longer be modified"):
        job_db.commit()
    job_db.rollback()


def test_unregistered_update_area_can_be_edited_and_deleted(
    job_db: sqlmodel.Session,
):
    area = UpdateArea(geom="Polygon((0 0, 1 0, 1 1, 0 1, 0 0))", dirty=False)
    job_db.add(area)
    job_db.commit()

    area.geom = "Polygon((0 0, 2 0, 2 2, 0 2, 0 0))"
    job_db.commit()

    job_db.delete(area)
    job_db.commit()


def test_deleting_dissolved_update_area_writes_restore_row(
    job_db: sqlmodel.Session,
):
    dissolved_geom = "Polygon((0 0, 3 0, 3 3, 0 3, 0 0))"
    area = UpdateArea(
        geom="Polygon((0 0, 1 0, 1 1, 0 1, 0 0))",
        dissolved_geom=dissolved_geom,
        dirty=False,
    )
    job_db.add(area)
    job_db.commit()

    job_db.delete(area)
    job_db.commit()

    restore_rows = job_db.exec(sqlmodel.select(UpdateAreaRestore)).all()
    assert len(restore_rows) == 1
    assert to_shape(restore_rows[0].geom).equals(to_shape(WKTElement(dissolved_geom)))
