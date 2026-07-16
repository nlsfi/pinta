# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add elevation to update_area and update_area_suggestion tables

Revision ID: 013
Revises: 012
Create Date: 2026-07-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str | Sequence[str] | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "elevation"
_TABLES = (
    ("user_data", "update_area"),
    ("reference", "update_area_suggestion"),
)


def upgrade() -> None:
    """Upgrade schema."""
    for schema, table in _TABLES:
        op.add_column(
            table,
            sa.Column(_COLUMN, sa.Float(), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for schema, table in _TABLES:
        op.drop_column(table, _COLUMN, schema=schema)
