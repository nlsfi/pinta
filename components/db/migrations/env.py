# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Module to confugre Alembic migrations.

env.py module is used to configure, create and run database
 migrations for a certain database.

If there is need to set up multiple different databases,
make separate migration folders for each.
"""

import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from dotenv import load_dotenv
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool, text
from sqlmodel import SQLModel

from pinta_db.models.all import *  # noqa: F403
from pinta_db.schemas import (
    SCHEMA_CONFIGURATIONS,
    Privilege,
    Role,
    RolePrivileges,
    Schema,
    SchemaConfig,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.engine.base import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = SQLModel.metadata

load_dotenv()

# Read env variables
ADMIN_DB_USERNAME = os.getenv("DB_ADMIN_USER")
ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD")
HOST = os.getenv("DB_HOST")
PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DB_OWNER_ROLE = os.getenv("DB_OWNER_ROLE")
DB_WRITER_ROLE = os.getenv("DB_WRITER_ROLE")
DB_READER_ROLE = os.getenv("DB_READER_ROLE")

config.set_main_option(
    "sqlalchemy.url",
    f"postgresql+psycopg://{ADMIN_DB_USERNAME}:{ADMIN_PASSWORD}@{HOST}:{PORT}/{DB_NAME}",
)


def _grant_list(privileges: "Iterable[Privilege]") -> str:
    return ", ".join(x.name for x in privileges)


def _get_create_schema_statement(schema_config: "SchemaConfig") -> list[str]:
    schema = schema_config.schema.value
    return [
        f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {DB_OWNER_ROLE}",
        f"GRANT {_grant_list(schema_config.owner_privileges)} "
        f"ON SCHEMA {schema} TO {DB_OWNER_ROLE}",
    ]


def _get_set_schema_role_privileges(
    schema_config: "SchemaConfig", role_config: "RolePrivileges"
) -> list[str]:
    schema = schema_config.schema.value
    if role_config.role == Role.WRITER:
        role = DB_WRITER_ROLE
    elif role_config.role == Role.READER:
        role = DB_OWNER_ROLE
    else:
        raise ValueError

    statements: list[str] = []

    if role_config.usage:
        statements.append(f"GRANT USAGE ON SCHEMA {schema} TO {role}")

    if role_config.table_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.table_privileges)} "
            f"ON ALL TABLES IN SCHEMA {schema} TO {role}"
        )

    if role_config.sequence_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.sequence_privileges)} "
            f"ON ALL SEQUENCES IN SCHEMA {schema} TO {role}"
        )

    if role_config.default_table_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{DB_OWNER_ROLE} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_table_privileges)} "
            f"ON TABLES TO {role}"
        )

    if role_config.default_sequence_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{DB_OWNER_ROLE} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_sequence_privileges)} "
            f"ON SEQUENCES TO {role}"
        )

    return statements


def create_schemas_and_schema_privileges(
    connection: "Connection",
) -> None:
    """Ensure that the schemas and shcmea privileges are set up."""
    statements: list[str] = []

    for schema_config in SCHEMA_CONFIGURATIONS:
        statements.extend(_get_create_schema_statement(schema_config))

        for role_config in schema_config.role_privileges:
            statements.extend(
                _get_set_schema_role_privileges(schema_config, role_config)
            )

    for statement in statements:
        connection.execute(text(statement))


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        create_schemas_and_schema_privileges(connection)
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table_schema=Schema.MIGRATIONS.value,
            # PostGIS and Geoalchemy stuff
            include_object=alembic_helpers.include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
