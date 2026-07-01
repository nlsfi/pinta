# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

import sqlmodel
from sqlalchemy import bindparam

from pinta_db_utils import database_utils, engine_utils

PINTA_MANAGED_SCHEMAS = ("dem", "management", "reference", "user_data")


def _create_from_template(
    db_name: str, template_name: str, admin_credentials: engine_utils.Credentials
) -> None:
    with engine_utils.get_autocommit_connection(admin_credentials) as connection:
        # replace_existing so each test session starts from a clean clone; the
        # advisory lock inside handles pytest-xdist race conditions.
        database_utils.initialize_db_from_template(
            connection, db_name, template_name, replace_existing=True
        )


def _truncate_pinta_schemas(credentials: engine_utils.Credentials) -> None:
    """Empty every table in the pinta-managed schemas of a cloned database."""
    list_tables = sqlmodel.text(
        "SELECT format('%I.%I', schemaname, tablename) "
        "FROM pg_tables WHERE schemaname IN :schemas"
    ).bindparams(bindparam("schemas", expanding=True))
    with engine_utils.get_autocommit_connection(credentials) as connection:
        tables = (
            connection.execute(list_tables, {"schemas": list(PINTA_MANAGED_SCHEMAS)})
            .scalars()
            .all()
        )
        if tables:
            connection.execute(
                sqlmodel.text(
                    f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
                )
            )


def get_primary_admin_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_PRIMARY_ADMIN_USER"],
        os.environ["DB_PRIMARY_ADMIN_PASSWORD"],
        os.environ["DB_PRIMARY_HOST"],
        os.environ["DB_PRIMARY_PORT"],
        db_name,
    )


def get_job_admin_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get admin connection parameters for the job db."""
    return engine_utils.Credentials(
        os.environ["DB_JOB_ADMIN_USER"],
        os.environ["DB_JOB_ADMIN_PASSWORD"],
        os.environ["DB_JOB_HOST"],
        os.environ["DB_JOB_PORT"],
        db_name,
    )


def get_primary_writer_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_PRIMARY_EDITOR_USER"],
        os.environ["DB_PRIMARY_EDITOR_PASSWORD"],
        os.environ["DB_PRIMARY_HOST"],
        os.environ["DB_PRIMARY_PORT"],
        db_name,
    )


def get_primary_processing_worker_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_PRIMARY_PROCESSING_WORKER_USER"],
        os.environ["DB_PRIMARY_PROCESSING_WORKER_PASSWORD"],
        os.environ["DB_PRIMARY_HOST"],
        os.environ["DB_PRIMARY_PORT"],
        db_name,
    )


def create_primary_db(worker_id: str) -> str:
    """Create a new database for the test session."""
    db_name = os.environ["DB_PRIMARY_NAME"] + f"_test_{worker_id}"
    _create_from_template(
        db_name,
        os.environ["DB_PRIMARY_NAME"],
        get_primary_admin_credentials("postgres"),
    )
    _truncate_pinta_schemas(get_primary_admin_credentials(db_name))
    return db_name


def create_job_db(worker_id: str) -> str:
    """Create a new database for the test session."""
    db_name = f"test_job_{worker_id}"
    _create_from_template(
        db_name,
        os.environ["DB_JOB_TEMPLATE_NAME"],
        get_job_admin_credentials("postgres"),
    )
    _truncate_pinta_schemas(get_job_admin_credentials(db_name))
    return db_name
