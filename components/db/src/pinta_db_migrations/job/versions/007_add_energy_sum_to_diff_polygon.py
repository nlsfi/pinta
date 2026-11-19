# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add energy_sum column to diff_polygon table

Revision ID: 007
Revises: 006
Create Date: 2026-06-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | Sequence[str] | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "diff_polygon",
        sa.Column("energy_sum", sa.Float(), nullable=True),
        schema="reference",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("diff_polygon", "energy_sum", schema="reference")
