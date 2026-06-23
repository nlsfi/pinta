# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add raster constraints to base reference tables

Revision ID: 004
Revises: 003
Create Date: 2026-06-23

"""

import os
from collections.abc import Sequence

from migrations import _schema_op
from pinta_db import env

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_TABLES = ("dem", "diff", "diff_dior")
_OWNER = os.environ["DB_JOB_OWNER_ROLE"]
_PROCESSING_WORKER = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]


def upgrade() -> None:
    """Upgrade schema."""
    srid = int(env.SRID)
    pixel_size = env.DEM_PIXEL_SIZE
    nodata = env.DEM_NODATA

    for table in _BASE_TABLES:
        _schema_op.add_raster_constraints_to_existing_table(
            table, pixel_size, nodata, srid, schema="reference"
        )

    _schema_op.grant_privileges_on_schema(
        schema="reference", role=_PROCESSING_WORKER, privileges=("USAGE", "CREATE")
    )
    _schema_op.grant_default_privileges_on_sequences_in_schema(
        schema="reference",
        schema_owner=_OWNER,
        role=_PROCESSING_WORKER,
        privileges=("USAGE", "SELECT"),
    )
    _schema_op.grant_default_privileges_on_tables_in_schema(
        schema="reference",
        schema_owner=_OWNER,
        role=_PROCESSING_WORKER,
        privileges=("INSERT", "SELECT", "UPDATE", "DELETE"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    _schema_op.revoke_all_tables_privileges_in_schema(
        schema="reference",
        role=_PROCESSING_WORKER,
        privileges=("INSERT", "SELECT", "UPDATE", "DELETE"),
    )
    _schema_op.revoke_default_privileges_on_tables_in_schema(
        schema="reference",
        schema_owner=_OWNER,
        role=_PROCESSING_WORKER,
        privileges=("INSERT", "SELECT", "UPDATE", "DELETE"),
    )
    _schema_op.revoke_default_privileges_on_sequences_in_schema(
        schema="reference",
        schema_owner=_OWNER,
        role=_PROCESSING_WORKER,
        privileges=("USAGE", "SELECT"),
    )
    _schema_op.revoke_privileges_on_schema(
        schema="reference", role=_PROCESSING_WORKER, privileges=("USAGE", "CREATE")
    )

    for table in reversed(_BASE_TABLES):
        _schema_op.drop_raster_constraints_from_existing_table(
            table, schema="reference"
        )
