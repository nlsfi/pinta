# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add dirty flag to update_area table

Revision ID: 010
Revises: 009
Create Date: 2026-07-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str | Sequence[str] | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "user_data"
_TABLE = "update_area"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        _TABLE,
        sa.Column(
            "dirty",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(_TABLE, "dirty", schema=_SCHEMA)
