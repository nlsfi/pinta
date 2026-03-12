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

# Get env variables before importing models
load_dotenv()

from sqlalchemy import Connection, engine_from_config, pool, text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from pinta_db.models.all import *  # noqa: F403, E402
from pinta_db.schemas import (  # noqa: E402
    SCHEMA_CONFIGURATIONS,
    Schema,
)
from pinta_db_utils import schema_utils  # noqa: E402
from pinta_db_utils.engine_utils import Credentials  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = SQLModel.metadata


# Read env variables
ADMIN_CREDENTIALS = Credentials(
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
        SCHEMA_CONFIGURATIONS,
        schema_utils.Roles(
            owner=DB_OWNER_ROLE,
            writer=DB_WRITER_ROLE,
            reader=DB_READER_ROLE,
        ),
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

        _setup_schemas(connection)
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
