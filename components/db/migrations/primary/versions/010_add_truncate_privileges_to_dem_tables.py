# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add truncate privileges to dem tables

Revision ID: 010
Revises: 009
Create Date: 2026-08-25

"""

import os
from collections.abc import Sequence

from migrations import _schema_op as schema_op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str | Sequence[str] | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = os.environ["DB_PRIMARY_OWNER_ROLE"]
PROCESSING_WORKER = os.environ["DB_PRIMARY_PROCESSING_WORKER_ROLE"]

DEM_SCHEMA = "dem"
DEM_TABLES = ("dem", "o_2_dem", "o_8_dem", "o_128_dem")


def upgrade() -> None:
    """Upgrade schema."""
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=DEM_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("TRUNCATE",),
    )
    for table in DEM_TABLES:
        schema_op.grant_privileges_on_table(
            schema=DEM_SCHEMA,
            table=table,
            role=PROCESSING_WORKER,
            privileges=("TRUNCATE",),
        )


def downgrade() -> None:
    """Downgrade schema."""
    schema_op.revoke_default_privileges_on_tables_in_schema(
        schema=DEM_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("TRUNCATE",),
    )
    schema_op.revoke_all_tables_privileges_in_schema(
        schema=DEM_SCHEMA,
        role=PROCESSING_WORKER,
        privileges=("TRUNCATE",),
    )
