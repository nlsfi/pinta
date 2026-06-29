# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Rename diff and diff_dior tables to diff_gt_threshold and diff_lte_threshold

Revision ID: 006
Revises: 005
Create Date: 2026-06-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations import _schema_op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | Sequence[str] | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OVERVIEW_FACTORS = (2, 8, 128)
_RENAMED_TABLES = (
    ("diff", "diff_gt_threshold"),
    ("diff_dior", "diff_lte_threshold"),
)


def _rename_overview(
    old_overview: str,
    new_overview: str,
    factor: int,
    new_base_table: str,
) -> None:
    op.rename_table(old_overview, new_overview, schema="reference")
    op.execute(
        f"ALTER INDEX reference.idx_{old_overview}_rast"
        f" RENAME TO idx_{new_overview}_rast"
    )
    op.execute(
        f"ALTER TABLE reference.{new_overview} RENAME CONSTRAINT"
        f' "pk_{old_overview}" TO "pk_{new_overview}"'
    )
    op.execute(
        f"ALTER TABLE reference.{new_overview} RENAME CONSTRAINT"
        f' "enforce_spatially_unique_{old_overview}_rast"'
        f' TO "enforce_spatially_unique_{new_overview}_rast"'
    )
    op.execute(
        f"ALTER TABLE reference.{new_overview} RENAME CONSTRAINT"
        f' "enforce_coverage_tile_{old_overview}_rast"'
        f' TO "enforce_coverage_tile_{new_overview}_rast"'
    )
    # The overview constraint body embeds the base table name as a string literal;
    # drop and re-add so it references the renamed base table.
    op.execute(
        sa.text("SELECT DropOverviewConstraints(:schema, :table, 'rast')").bindparams(
            schema="reference", table=new_overview
        )
    )
    _schema_op.add_overview_constraints(
        "reference", new_overview, factor, new_base_table
    )


def _rename_base(old_table: str, new_table: str) -> None:
    op.rename_table(old_table, new_table, schema="reference")
    op.execute(
        f"ALTER INDEX reference.idx_{old_table}_rast RENAME TO idx_{new_table}_rast"
    )
    op.execute(
        f"ALTER TABLE reference.{new_table} RENAME CONSTRAINT"
        f' "enforce_spatially_unique_{old_table}_rast"'
        f' TO "enforce_spatially_unique_{new_table}_rast"'
    )
    op.execute(
        f"ALTER TABLE reference.{new_table} RENAME CONSTRAINT"
        f' "enforce_coverage_tile_{old_table}_rast"'
        f' TO "enforce_coverage_tile_{new_table}_rast"'
    )


def upgrade() -> None:
    """Upgrade schema."""
    for old_table, new_table in _RENAMED_TABLES:
        for factor in _OVERVIEW_FACTORS:
            _rename_overview(
                f"o_{factor}_{old_table}",
                f"o_{factor}_{new_table}",
                factor,
                new_table,
            )
        _rename_base(old_table, new_table)


def downgrade() -> None:
    """Downgrade schema."""
    for old_table, new_table in reversed(_RENAMED_TABLES):
        for factor in reversed(_OVERVIEW_FACTORS):
            _rename_overview(
                f"o_{factor}_{new_table}",
                f"o_{factor}_{old_table}",
                factor,
                old_table,
            )
        _rename_base(new_table, old_table)
