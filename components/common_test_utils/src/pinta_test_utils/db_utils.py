# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

from pinta_db.schemas import SCHEMA_CONFIGURATIONS
from pinta_db_utils import engine_utils, schema_utils
from sqlmodel import text


def get_admin_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_ADMIN_USER"],
        os.environ["DB_ADMIN_PASSWORD"],
        os.environ["DB_HOST"],
        os.environ["DB_PORT"],
        db_name,
    )


def get_writer_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_EDITOR_USER"],
        os.environ["DB_EDITOR_PASSWORD"],
        os.environ["DB_HOST"],
        os.environ["DB_PORT"],
        db_name,
    )


def create_db(worker_id: str) -> str:
    """Create a new database for the test session."""
    db_name = os.environ["DB_NAME"] + f"_test_{worker_id}"
    template_name = os.environ["DB_NAME"] + "_test_template"
    db_roles = schema_utils.Roles(
        owner=os.environ["DB_OWNER_ROLE"],
        writer=os.environ["DB_WRITER_ROLE"],
        reader=os.environ["DB_READER_ROLE"],
    )

    kill_connections_query = text(
        "SELECT pg_terminate_backend(pg_stat_activity.pid) "  # noqa: S608
        "FROM pg_stat_activity "
        f"WHERE pg_stat_activity.datname = '{db_name}' "
        "AND pid <> pg_backend_pid()"
    )

    with engine_utils.get_autocommit_connection(
        get_admin_credentials(os.environ["DB_NAME"])
    ) as connection:
        connection.execute(kill_connections_query)
        connection.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        connection.execute(
            text(f"CREATE DATABASE {db_name} WITH TEMPLATE {template_name}")
        )

    schema_statements = schema_utils.get_set_schema_role_privileges_statements(
        SCHEMA_CONFIGURATIONS, db_roles
    )

    with engine_utils.get_autocommit_connection(
        get_admin_credentials(db_name)
    ) as connection:
        for statement in schema_statements:
            connection.execute(text(statement))

    return db_name
