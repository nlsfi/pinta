# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

import pytest
import sqlalchemy as sa
import sqlmodel

from pinta_db import exceptions
from pinta_db.job_db import privileges
from pinta_db.job_db.models import user
from pinta_db_utils import model_utils, privilege_utils

_WRITER_ROLE = os.environ["DB_JOB_WRITER_ROLE"]
_READER_ROLE = os.environ["DB_JOB_READER_ROLE"]
_PROCESSING_WORKER_ROLE = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]

_GEOM = "Polygon((0 0, 1 0, 1 1, 0 1, 0 0))"


def _writes_as(session: sqlmodel.Session, role: str) -> bool:
    """Return whether ``role`` can insert into update_area."""
    session.exec(sa.text(f'SET ROLE "{role}"'))  # type: ignore[call-overload]
    try:
        session.add(user.UpdateArea(geom=_GEOM))
        session.commit()
    except sa.exc.ProgrammingError:
        session.rollback()
        return False
    else:
        return True
    finally:
        session.exec(sa.text("RESET ROLE"))  # type: ignore[call-overload]


def _can_read(session: sqlmodel.Session, role: str) -> bool:
    schema, table = model_utils.schema_and_table(user.UpdateArea)
    return privilege_utils.role_has_all_table_privileges(
        session, schema, table, role, ("SELECT",)
    )


def test_revoke_and_restore_update_area_write_access(job_db: sqlmodel.Session):
    assert _writes_as(job_db, _WRITER_ROLE)

    privileges.revoke_update_area_write_access(job_db, _WRITER_ROLE)
    assert not _writes_as(job_db, _WRITER_ROLE)

    privileges.restore_update_area_write_access(job_db, _WRITER_ROLE)
    assert _writes_as(job_db, _WRITER_ROLE)


def test_revoke_keeps_writer_read_access(job_db: sqlmodel.Session):
    privileges.revoke_update_area_write_access(job_db, _WRITER_ROLE)

    # Editors keep seeing the layer in QGIS while they cannot edit it.
    assert _can_read(job_db, _WRITER_ROLE)


def test_revoke_leaves_other_roles_alone(job_db: sqlmodel.Session):
    privileges.revoke_update_area_write_access(job_db, _WRITER_ROLE)

    # The dissolve itself runs as the processing worker, so it must keep writing.
    assert _writes_as(job_db, _PROCESSING_WORKER_ROLE)
    assert _can_read(job_db, _READER_ROLE)


def test_restore_is_idempotent(job_db: sqlmodel.Session):
    privileges.restore_update_area_write_access(job_db, _WRITER_ROLE)

    assert _writes_as(job_db, _WRITER_ROLE)


def test_revoke_from_unknown_role_raises(job_db: sqlmodel.Session):
    with pytest.raises(exceptions.MissingRoleError):
        privileges.revoke_update_area_write_access(job_db, "no_such_role")


def test_revoke_by_non_grantor_raises(job_db: sqlmodel.Session):
    """A REVOKE Postgres only warns about must not look like a successful lock."""
    job_db.exec(sa.text(f'SET ROLE "{_PROCESSING_WORKER_ROLE}"'))  # type: ignore[call-overload]
    try:
        with pytest.raises(exceptions.PrivilegeChangeError):
            privileges.revoke_update_area_write_access(job_db, _WRITER_ROLE)
    finally:
        job_db.rollback()
        job_db.exec(sa.text("RESET ROLE"))  # type: ignore[call-overload]

    assert _writes_as(job_db, _WRITER_ROLE)


def test_unsupported_privilege_rejected(job_db: sqlmodel.Session):
    schema, table = model_utils.schema_and_table(user.UpdateArea)
    with pytest.raises(ValueError, match="Unsupported table privileges"):
        privilege_utils.revoke_table_privileges(
            job_db, schema, table, _WRITER_ROLE, ("INSERT; DROP TABLE x",)
        )
