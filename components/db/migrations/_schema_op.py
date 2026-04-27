# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import textwrap

from alembic import op

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
