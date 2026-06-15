# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import textwrap

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Raster

from pinta_db.primary_db.models import dem

"""
DO NOT MODIFY THE FUNCTIONS DIRECTLY,
ADD NEW FUNCTIONS INSTEAD!
"""


def create_schema(
    schema: str,
    owner: str,
) -> None:
    """Create a new schema with the specified owner."""
    op.execute(f"CREATE SCHEMA {schema} AUTHORIZATION {owner}")


def drop_schema(schema: str) -> None:
    """Drop the specified schema."""
    op.execute(f"DROP SCHEMA {schema} CASCADE")


def create_role(role: str) -> None:
    """Create a new NOLOGIN role and grant membership back to the creator."""
    op.execute(
        textwrap.dedent(
            f"""
    DO $$
        BEGIN
        CREATE ROLE {role} WITH NOLOGIN;
        EXCEPTION WHEN duplicate_object THEN RAISE NOTICE '%, skipping', SQLERRM USING ERRCODE = SQLSTATE;
        END
    $$;
    GRANT {role} TO CURRENT_USER WITH SET TRUE, INHERIT TRUE;
    """  # noqa: E501
        )
    )


def drop_role(role: str) -> None:
    """Drop the specified role."""
    op.execute(f"DROP ROLE {role}")


def grant_privileges_on_schema(
    schema: str,
    role: str,
    privileges: tuple[str, ...],
) -> None:
    """Grant specified privileges on the schema to the role."""
    privileges_str = ", ".join(privileges)
    op.execute(f"GRANT {privileges_str} ON SCHEMA {schema} TO {role}")


def grant_privileges_on_table(
    schema: str,
    table: str,
    role: str,
    privileges: tuple[str, ...],
) -> None:
    """Grant specified privileges on an existing table to the role."""
    privileges_str = ", ".join(privileges)
    op.execute(f"GRANT {privileges_str} ON TABLE {schema}.{table} TO {role}")


def grant_default_privileges_on_tables_in_schema(
    schema: str,
    schema_owner: str,
    role: str,
    privileges: tuple[str, ...],
    grant_option: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Grant specified default privileges on tables in the schema to the role."""
    privileges_str = ", ".join(privileges)
    grant_option_str = " WITH GRANT OPTION" if grant_option else ""
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {schema_owner} IN SCHEMA {schema} "
        f"GRANT {privileges_str} ON TABLES TO {role}{grant_option_str}"
    )


def grant_default_privileges_on_sequences_in_schema(
    schema: str,
    schema_owner: str,
    role: str,
    privileges: tuple[str, ...],
    grant_option: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Grant specified default privileges on sequences in the schema to the role."""
    privileges_str = ", ".join(privileges)
    grant_option_str = " WITH GRANT OPTION" if grant_option else ""
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {schema_owner} IN SCHEMA {schema} "
        f"GRANT {privileges_str} ON SEQUENCES TO {role}{grant_option_str}"
    )


def grant_role_to_role(role: str, target: str) -> None:
    """Grant role membership to the target role."""
    op.execute(f"GRANT {role} TO {target}")


def revoke_role_from_role(role: str, target: str) -> None:
    """Revoke role membership from the target role."""
    op.execute(f"REVOKE {role} FROM {target}")


def grant_database_privileges(
    db_name: str,
    role: str,
    privileges: tuple[str, ...],
) -> None:
    """Grant specified privileges on the database to the role."""
    privileges_str = ", ".join(privileges)
    op.execute(f"GRANT {privileges_str} ON DATABASE {db_name} TO {role}")


def revoke_all_on_database_from_public(db_name: str) -> None:
    """Revoke all privileges on the database from PUBLIC."""
    op.execute(f"REVOKE ALL ON DATABASE {db_name} FROM PUBLIC")


def _make_empty_raster(  # noqa: PLR0913
    schema: str,
    table: str,
    upper_left_x: int,
    upper_left_y: int,
    nodata: int,
    pixel_size: int,
    srid: int,
) -> sa.TextClause:
    bind = op.get_bind()
    quoted_table = bind.dialect.identifier_preparer.quote(table)
    return sa.text(f"""
                   INSERT INTO "{schema}".{quoted_table} ("rast")
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


def _add_raster_constraints(schema: str, table: str) -> sa.TextClause:
    # Disabled constraints:
    # - enforce regularly blocking arrangement (generated manually)
    return sa.text("""
        SELECT AddRasterConstraints(
            :schema, :table, 'rast', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
            FALSE, TRUE, TRUE, TRUE, TRUE, TRUE
        )
        """).bindparams(schema=schema, table=table)


def add_overview_constraints(
    schema: str, table: str, factor: int, main_table: str
) -> None:
    """Link an overview table to its base raster table."""
    op.execute(
        sa.text("""
            SELECT AddOverviewConstraints(
                :schema, :table, 'rast', :schema, :main_table, 'rast', :factor
            );
            """).bindparams(
            schema=schema, table=table, factor=factor, main_table=main_table
        )
    )


def _delete_all_rasters(schema: str, table: str) -> sa.TextClause:
    bind = op.get_bind()
    quoted_table = bind.dialect.identifier_preparer.quote(table)
    # TRUNCATE instead of DELETE: no dead tuples means autovacuum won't connect
    # to job_template during tests and block the DROP/CREATE DATABASE sequence.
    return sa.text(f'TRUNCATE "{schema}".{quoted_table}')


def create_raster_table(
    table: str,
    pixel_size: int,
    nodata: int,
    srid: int,
    schema: str = "reference",
) -> None:
    """Create a PostGIS raster table with constraints and seed tiles."""
    tile_size = pixel_size * 256

    op.create_geospatial_table(
        table,
        sa.Column("rid", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "rast",
            Raster(
                spatial_index=False, from_text="raster", name="raster", nullable=False
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid", name=op.f(f"pk_{table}")),
        schema=schema,
    )
    op.create_index(
        f"idx_{table}_rast",
        table,
        [sa.literal_column("ST_ConvexHull(rast)")],
        unique=False,
        schema=schema,
        postgresql_using="gist",
    )
    op.execute(
        dem.constraint_enforce_spatially_unique_dem_rast(
            table, f"enforce_spatially_unique_{table}_rast", schema=schema
        )
    )
    op.execute(
        dem.constraint_enforce_coverage_tile_dem_rast(
            table, f"enforce_coverage_tile_{table}_rast", tile_size, schema=schema
        )
    )
    op.execute(
        _make_empty_raster(schema, table, 41248, 7880720, nodata, pixel_size, srid)
    )
    op.execute(
        _make_empty_raster(
            schema,
            table,
            762144 - tile_size,
            6570000 + tile_size,
            nodata,
            pixel_size,
            srid,
        )
    )
    op.execute(_add_raster_constraints(schema, table))
    op.execute(_delete_all_rasters(schema, table))
