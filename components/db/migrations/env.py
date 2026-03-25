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

import logging.config
import os
import typing

import alembic
import dotenv
import geoalchemy2.alembic_helpers

# Get env variables before importing models
dotenv.load_dotenv()

import sqlalchemy  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import pinta_db_utils.alembic_helpers  # noqa: E402
from pinta_db import schemas  # noqa: E402
from pinta_db.models.all import *  # noqa: F403, E402
from pinta_db_utils import engine_utils, schema_utils  # noqa: E402

if typing.TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection

config = alembic.context.config

if config.config_file_name is not None:
    logging.config.fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Read env variables
ADMIN_CREDENTIALS = engine_utils.Credentials(
    os.environ["DB_ADMIN_USER"],
    os.environ["DB_ADMIN_PASSWORD"],
    os.environ["DB_HOST"],
    os.environ["DB_PORT"],
    os.environ["DB_NAME"],
)

DB_OWNER_ROLE = os.environ["DB_OWNER_ROLE"]
DB_WRITER_ROLE = os.environ["DB_WRITER_ROLE"]
DB_READER_ROLE = os.environ["DB_READER_ROLE"]

config.set_main_option("sqlalchemy.url", ADMIN_CREDENTIALS.get_connection_string())


def _setup_schemas(connection: "Connection") -> None:
    statements = schema_utils.get_set_schema_role_privileges_statements(
        schemas.SCHEMA_CONFIGURATIONS,
        schema_utils.Roles(
            owner=DB_OWNER_ROLE,
            writer=DB_WRITER_ROLE,
            reader=DB_READER_ROLE,
        ),
    )

    for statement in statements:
        connection.execute(sqlalchemy.text(statement))


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = sqlalchemy.engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=sqlalchemy.pool.NullPool,
    )

    with connectable.connect() as connection:
        alembic.context.configure(
            connection=connection, target_metadata=target_metadata
        )

        _setup_schemas(connection)
        connection.commit()

        alembic.context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table_schema=schemas.Schema.MIGRATIONS.value,
            # PostGIS and Geoalchemy stuff
            include_object=geoalchemy2.alembic_helpers.include_object,
            process_revision_directives=geoalchemy2.alembic_helpers.writer,
            render_item=pinta_db_utils.alembic_helpers.render_item,
        )

        with alembic.context.begin_transaction():
            alembic.context.run_migrations()


run_migrations_online()
