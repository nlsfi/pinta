# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""DEM models."""

import sqlalchemy as sa

from pinta_db.common.base import BaseMainDb
from pinta_db.main_db.models.base import DemBase


class Dem(BaseMainDb, DemBase, table=True):  # type: ignore[call-arg]
    """Elevation model."""


class O2Dem(BaseMainDb, DemBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8Dem(BaseMainDb, DemBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128Dem(BaseMainDb, DemBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""


def constraint_enforce_spatially_unique_dem_rast(table: str, name: str) -> sa.DDL:
    """Enforce DEM tiles are spatially unique."""
    from alembic import op  # noqa: PLC0415

    bind = op.get_bind()
    preparer = bind.dialect.identifier_preparer
    quoted_table = preparer.quote(table)
    quoted_name = preparer.quote(name)

    return sa.DDL(f"""
        ALTER TABLE "dem".{quoted_table}
        ADD CONSTRAINT {quoted_name}
        EXCLUDE USING btree ((rast::geometry) WITH =);
        """)


def constraint_enforce_coverage_tile_dem_rast(
    table: str, name: str, tile_size: int
) -> sa.DDL:
    """Enforce DEM tiles are located on a grid of tile map unit size."""
    from alembic import op  # noqa: PLC0415

    bind = op.get_bind()
    preparer = bind.dialect.identifier_preparer
    quoted_table = preparer.quote(table)
    quoted_name = preparer.quote(name)

    return sa.DDL(f"""
        ALTER TABLE "dem".{quoted_table}
        ADD CONSTRAINT {quoted_name} CHECK (
            COALESCE(
                st_iscoveragetile(null, null, 0, 0),
                (
                    mod(st_upperleftx(rast)::numeric - 500000, {tile_size}) = 0
                    AND mod(st_upperlefty(rast)::numeric - 6570000, {tile_size}) = 0
                )
            )
        );
        """)
