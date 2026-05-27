# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add backend role

Revision ID: 006
Revises: 005_add_processing_status
Create Date: 2026-05-28 09:26:37.369532

"""

import os
from collections.abc import Sequence

from migrations import _schema_op as schema_op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | Sequence[str] | None = "005_add_processing_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKEND = os.environ["DB_PRIMARY_BACKEND_ROLE"]
DB_NAME = os.environ["DB_PRIMARY_NAME"]

MANAGEMENT_SCHEMA = "management"
PRODUCTION_AREA_TABLE = "production_area"


def upgrade() -> None:
    """Upgrade schema."""
    schema_op.create_role(BACKEND)
    schema_op.grant_database_privileges(DB_NAME, BACKEND, ("CONNECT", "TEMP"))
    schema_op.grant_privileges_on_schema(
        schema=MANAGEMENT_SCHEMA, role=BACKEND, privileges=("USAGE",)
    )
    schema_op.grant_privileges_on_table(
        schema=MANAGEMENT_SCHEMA,
        table=PRODUCTION_AREA_TABLE,
        role=BACKEND,
        privileges=("SELECT", "UPDATE"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    schema_op.drop_role(BACKEND)
