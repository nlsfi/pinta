# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add dem preview tables

Revision ID: 008
Revises: 007
Create Date: 2026-07-02

"""

from collections.abc import Sequence

from alembic import op

from migrations import _schema_op
from pinta_common import Settings

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | Sequence[str] | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OVERVIEW_FACTORS = (2, 8, 128)
_BASE_TABLE = "dem_preview"


def upgrade() -> None:
    """Upgrade schema."""
    srid = int(Settings.DB_SRID)
    pixel_size = Settings.DB_DEM_PIXEL_SIZE
    nodata = Settings.DB_DEM_NODATA

    _schema_op.create_raster_table(
        _BASE_TABLE, pixel_size, nodata, srid, schema="user_data"
    )
    for factor in _OVERVIEW_FACTORS:
        table = f"o_{factor}_{_BASE_TABLE}"
        _schema_op.create_raster_table(
            table, pixel_size * factor, nodata, srid, schema="user_data"
        )
        _schema_op.add_overview_constraints("user_data", table, factor, _BASE_TABLE)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(f"idx_{_BASE_TABLE}_rast", table_name=_BASE_TABLE, schema="user_data")
    op.drop_geospatial_table(_BASE_TABLE, schema="user_data")
    for factor in reversed(_OVERVIEW_FACTORS):
        table = f"o_{factor}_{_BASE_TABLE}"
        op.drop_index(f"idx_{table}_rast", table_name=table, schema="user_data")
        op.drop_geospatial_table(table, schema="user_data")
