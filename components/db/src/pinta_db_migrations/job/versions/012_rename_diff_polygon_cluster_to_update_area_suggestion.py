# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Rename diff_polygon_cluster table to update_area_suggestion

Revision ID: 012
Revises: 011
Create Date: 2026-07-15

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "reference"
_OLD_TABLE = "diff_polygon_cluster"
_NEW_TABLE = "update_area_suggestion"


def _rename(old_table: str, new_table: str) -> None:
    op.rename_table(old_table, new_table, schema=_SCHEMA)
    op.execute(
        f"ALTER INDEX {_SCHEMA}.idx_{old_table}_geom RENAME TO idx_{new_table}_geom"
    )
    # The primary key kept the Postgres default name when the table was created.
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{new_table} RENAME CONSTRAINT"
        f' "{old_table}_pkey" TO "{new_table}_pkey"'
    )


def upgrade() -> None:
    """Upgrade schema."""
    _rename(_OLD_TABLE, _NEW_TABLE)


def downgrade() -> None:
    """Downgrade schema."""
    _rename(_NEW_TABLE, _OLD_TABLE)
