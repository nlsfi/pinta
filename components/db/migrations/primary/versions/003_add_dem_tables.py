# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add dem tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-08 07:36:59.835976

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Raster

from pinta_common import Settings
from pinta_db.primary_db.models import dem

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _make_empty_raster(  # noqa: PLR0913
    table: str,
    upper_left_x: int,
    upper_left_y: int,
    nodata: int,
    pixel_size: int,
    srid: int,
) -> Any:  # noqa: ANN401
    bind = op.get_bind()
    preparer = bind.dialect.identifier_preparer
    quoted_table = preparer.quote(table)

    return sa.text(f"""
                   INSERT INTO "dem".{quoted_table} ("rast")
                   SELECT ST_AddBand(
                              ST_MakeEmptyRaster(
                                  256, 256, :upper_left_x, :upper_left_y,
                                  :pixel_size, :negative_pixel_size, 0, 0, :srid
                              ),
                              1,
                              '32BF'::text,
                              0,
                              :nodata
                          )
                   """).bindparams(
        upper_left_x=upper_left_x,
        upper_left_y=upper_left_y,
        pixel_size=pixel_size,
        negative_pixel_size=-pixel_size,
        srid=srid,
        nodata=nodata,
    )


def _add_raster_constraints(table: str) -> Any:  # noqa: ANN401
    # Disabled constraints:
    # - enforce regularly blocking arrangement (generated manually)
    return sa.text("""
        SELECT AddRasterConstraints(
            'dem', :table, 'rast', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
            FALSE, TRUE, TRUE, TRUE, TRUE, TRUE
        )
        """).bindparams(table=table)


def _add_overview_constraints(table: str, factor: int) -> Any:  # noqa: ANN401
    return sa.text("""
        SELECT AddOverviewConstraints(
            'dem', :table, 'rast', 'dem', 'dem', 'rast', :factor
        );
        """).bindparams(table=table, factor=factor)


def upgrade() -> None:
    """Upgrade schema."""
    srid = int(Settings.DB_SRID)
    pixel_size = Settings.DB_DEM_PIXEL_SIZE
    nodata = Settings.DB_DEM_NODATA
    pixel_size_overview_2 = pixel_size * 2
    pixel_size_overview_8 = pixel_size * 8
    pixel_size_overview_128 = pixel_size * 128
    tile_size = pixel_size * 256
    tile_size_overview_2 = pixel_size_overview_2 * 256
    tile_size_overview_8 = pixel_size_overview_8 * 256
    tile_size_overview_128 = pixel_size_overview_128 * 256
    # dem
    op.create_geospatial_table(
        "dem",
        sa.Column("rid", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "rast",
            Raster(
                spatial_index=False, from_text="raster", name="raster", nullable=False
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid", name=op.f("pk_dem")),
        schema="dem",
    )
    op.create_index(
        "idx_dem_rast",
        "dem",
        [sa.literal_column("ST_ConvexHull(rast)")],
        unique=False,
        schema="dem",
        postgresql_using="gist",
    )
    # add the regularly blocking constraints manually since the
    # postgis-generated raster overview would be too large in pixel size
    # this will ensure the tiles are located on a grid of tile map unit size
    # for regularly-blocking arrangement
    # hack postgis stats via using st_iscoveragetile with null input, since
    # the regularly blocking constraint check is done
    # against checking the string representation
    # "LIKE '%st_iscoveragetile(%'", actual coverage raster cannot be used here
    # due to its size exceeding max allowed pixel size
    op.execute(
        dem.constraint_enforce_spatially_unique_dem_rast(
            "dem", "enforce_spatially_unique_dem_rast"
        )
    )
    op.execute(
        dem.constraint_enforce_coverage_tile_dem_rast(
            "dem", "enforce_coverage_tile_dem_rast", tile_size
        )
    )
    # add dummy data to the raster table to infer indices on it
    # (tile size, srid, alignment, out-db-state, value type, nodata, band count, etc.)
    op.execute(_make_empty_raster("dem", 41248, 7880720, nodata, pixel_size, srid))
    op.execute(
        _make_empty_raster(
            "dem", 762144 - tile_size, 6570000 + tile_size, nodata, pixel_size, srid
        )
    )
    op.execute(_add_raster_constraints("dem"))
    op.execute(sa.text('DELETE FROM "dem"."dem"'))
    # overview factor 2
    op.create_geospatial_table(
        "o_2_dem",
        sa.Column("rid", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "rast",
            Raster(
                spatial_index=False, from_text="raster", name="raster", nullable=False
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid", name=op.f("pk_o_2_dem")),
        schema="dem",
    )
    op.create_index(
        "idx_o_2_dem_rast",
        "o_2_dem",
        [sa.literal_column("ST_ConvexHull(rast)")],
        unique=False,
        schema="dem",
        postgresql_using="gist",
    )
    op.execute(
        dem.constraint_enforce_spatially_unique_dem_rast(
            "o_2_dem", "enforce_spatially_unique_o_2_dem_rast"
        )
    )
    op.execute(
        dem.constraint_enforce_coverage_tile_dem_rast(
            "o_2_dem", "enforce_coverage_tile_o_2_dem_rast", tile_size_overview_2
        )
    )
    op.execute(
        _make_empty_raster(
            "o_2_dem", 41248, 7880720, nodata, pixel_size_overview_2, srid
        )
    )
    op.execute(
        _make_empty_raster(
            "o_2_dem",
            762144 - tile_size_overview_2,
            6570000 + tile_size_overview_2,
            nodata,
            pixel_size_overview_2,
            srid,
        )
    )
    op.execute(_add_raster_constraints("o_2_dem"))
    op.execute(sa.text('DELETE FROM "dem"."o_2_dem"'))
    op.execute(_add_overview_constraints("o_2_dem", 2))
    # overview factor 8
    op.create_geospatial_table(
        "o_8_dem",
        sa.Column("rid", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "rast",
            Raster(
                spatial_index=False, from_text="raster", name="raster", nullable=False
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid", name=op.f("pk_o_8_dem")),
        schema="dem",
    )
    op.create_index(
        "idx_o_8_dem_rast",
        "o_8_dem",
        [sa.literal_column("ST_ConvexHull(rast)")],
        unique=False,
        schema="dem",
        postgresql_using="gist",
    )
    op.execute(
        dem.constraint_enforce_spatially_unique_dem_rast(
            "o_8_dem", "enforce_spatially_unique_o_8_dem_rast"
        )
    )
    op.execute(
        dem.constraint_enforce_coverage_tile_dem_rast(
            "o_8_dem", "enforce_coverage_tile_o_8_dem_rast", tile_size_overview_8
        )
    )
    op.execute(
        _make_empty_raster(
            "o_8_dem", 41248, 7880720, nodata, pixel_size_overview_8, srid
        )
    )
    op.execute(
        _make_empty_raster(
            "o_8_dem",
            762144 - tile_size_overview_8,
            6570000 + tile_size_overview_8,
            nodata,
            pixel_size_overview_8,
            srid,
        )
    )
    op.execute(_add_raster_constraints("o_8_dem"))
    op.execute(sa.text('DELETE FROM "dem"."o_8_dem"'))
    op.execute(_add_overview_constraints("o_8_dem", 8))
    # overview factor 128
    op.create_geospatial_table(
        "o_128_dem",
        sa.Column("rid", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "rast",
            Raster(
                spatial_index=False, from_text="raster", name="raster", nullable=False
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid", name=op.f("pk_o_128_dem")),
        schema="dem",
    )
    op.create_index(
        "idx_o_128_dem_rast",
        "o_128_dem",
        [sa.literal_column("ST_ConvexHull(rast)")],
        unique=False,
        schema="dem",
        postgresql_using="gist",
    )
    op.execute(
        dem.constraint_enforce_spatially_unique_dem_rast(
            "o_128_dem", "enforce_spatially_unique_o_128_dem_rast"
        )
    )
    op.execute(
        dem.constraint_enforce_coverage_tile_dem_rast(
            "o_128_dem", "enforce_coverage_tile_o_128_dem_rast", tile_size_overview_128
        )
    )
    op.execute(
        _make_empty_raster(
            "o_128_dem", 41248, 7880720, nodata, pixel_size_overview_128, srid
        )
    )
    op.execute(
        _make_empty_raster(
            "o_128_dem",
            762144 - tile_size_overview_128,
            6570000 + tile_size_overview_128,
            nodata,
            pixel_size_overview_128,
            srid,
        )
    )
    op.execute(_add_raster_constraints("o_128_dem"))
    op.execute(sa.text('DELETE FROM "dem"."o_128_dem"'))
    op.execute(_add_overview_constraints("o_128_dem", 128))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_geospatial_index(
        "idx_o_128_dem_rast",
        table_name="o_128_dem",
        schema="dem",
        postgresql_using="gist",
        column_name="rast",
    )
    op.drop_geospatial_table("o_128_dem", schema="dem")
    op.drop_geospatial_index(
        "idx_o_8_dem_rast",
        table_name="o_8_dem",
        schema="dem",
        postgresql_using="gist",
        column_name="rast",
    )
    op.drop_geospatial_table("o_8_dem", schema="dem")
    op.drop_geospatial_index(
        "idx_o_2_dem_rast",
        table_name="o_2_dem",
        schema="dem",
        postgresql_using="gist",
        column_name="rast",
    )
    op.drop_geospatial_table("o_2_dem", schema="dem")
    op.drop_geospatial_index(
        "idx_dem_rast",
        table_name="dem",
        schema="dem",
        postgresql_using="gist",
        column_name="rast",
    )
    op.drop_geospatial_table("dem", schema="dem")
