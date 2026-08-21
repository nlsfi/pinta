# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import sqlmodel

from pinta_db.job_db.models import user
from pinta_db_utils import model_utils, privilege_utils

UPDATE_AREA_WRITE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE")


def revoke_update_area_write_access(session: sqlmodel.Session, role: str) -> None:
    """Lock role out of editing update_area."""
    schema, table = model_utils.schema_and_table(user.UpdateArea)
    privilege_utils.revoke_table_privileges(
        session, schema, table, role, UPDATE_AREA_WRITE_PRIVILEGES
    )


def restore_update_area_write_access(session: sqlmodel.Session, role: str) -> None:
    """Give role its update_area write access back."""
    schema, table = model_utils.schema_and_table(user.UpdateArea)
    privilege_utils.grant_table_privileges(
        session, schema, table, role, UPDATE_AREA_WRITE_PRIVILEGES
    )
