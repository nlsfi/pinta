# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

import alembic
import geoalchemy2.alembic_helpers
import sqlalchemy
from alembic.config import Config
from sqlalchemy.sql.schema import MetaData

import pinta_db_utils.alembic_helpers

if typing.TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection


def _setup_migration_schema(connection: "Connection", schema: str) -> None:
    connection.execute(sqlalchemy.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))


def run_migrations_online(
    config: Config, target_metadata: MetaData, migration_schema: str
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

        _setup_migration_schema(connection, migration_schema)
        connection.commit()

        alembic.context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table_schema=migration_schema,
            # PostGIS and Geoalchemy stuff
            include_object=geoalchemy2.alembic_helpers.include_object,
            process_revision_directives=geoalchemy2.alembic_helpers.writer,
            render_item=pinta_db_utils.alembic_helpers.render_item,
        )

        with alembic.context.begin_transaction():
            alembic.context.run_migrations()
