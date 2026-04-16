# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import typing

import alembic
import geoalchemy2.alembic_helpers
import sqlalchemy
from alembic.config import Config
from sqlalchemy.sql.schema import MetaData

import pinta_db_utils.alembic_helpers
from pinta_db import schemas
from pinta_db.schemas import SchemaConfig
from pinta_db_utils import schema_utils

if typing.TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection


# Read env variables
ROLES = {
    schemas.Role.OWNER: os.environ["DB_OWNER_ROLE"],
    schemas.Role.WRITER: os.environ["DB_WRITER_ROLE"],
    schemas.Role.READER: os.environ["DB_READER_ROLE"],
    schemas.Role.PROCESSING_WORKER: os.environ["DB_PROCESSING_WORKER_ROLE"],
}


def _setup_schemas(
    connection: "Connection",
    schema_configuration: list[SchemaConfig],
) -> None:
    statements = schema_utils.get_set_schema_role_privileges_statements(
        schema_configuration=schema_configuration,
        roles=ROLES,
    )

    for statement in statements:
        connection.execute(sqlalchemy.text(statement))


def run_migrations_online(
    config: Config,
    target_metadata: MetaData,
    schema_configuration: list[SchemaConfig],
) -> None:
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

        _setup_schemas(connection, schema_configuration)
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
