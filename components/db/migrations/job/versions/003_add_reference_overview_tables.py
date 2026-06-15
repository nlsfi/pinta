# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add reference overview tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-11 05:46:28.749976

"""

from collections.abc import Sequence

from alembic import op

from migrations import _schema_op
from pinta_db import env

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OVERVIEW_FACTORS = (2, 8, 128)
_BASE_TABLES = ("dem", "diff", "diff_dior")


def upgrade() -> None:
    """Upgrade schema."""
    srid = int(env.SRID)
    pixel_size = env.DEM_PIXEL_SIZE
    nodata = env.DEM_NODATA

    for base_table in _BASE_TABLES:
        for factor in _OVERVIEW_FACTORS:
            table = f"o_{factor}_{base_table}"
            _schema_op.create_raster_table(table, pixel_size * factor, nodata, srid)
            _schema_op.add_overview_constraints("reference", table, factor, base_table)


def downgrade() -> None:
    """Downgrade schema."""
    for base_table in reversed(_BASE_TABLES):
        for factor in reversed(_OVERVIEW_FACTORS):
            table = f"o_{factor}_{base_table}"
            op.drop_index(f"idx_{table}_rast", table_name=table, schema="reference")
            op.drop_geospatial_table(table, schema="reference")
