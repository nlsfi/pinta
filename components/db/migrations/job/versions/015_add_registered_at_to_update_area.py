# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add registered_at to update_area

Revision ID: 015
Revises: 014
Create Date: 2026-08-31 11:34:22.644781

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: str | Sequence[str] | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "update_area",
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        schema="user_data",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("update_area", "registered_at", schema="user_data")
