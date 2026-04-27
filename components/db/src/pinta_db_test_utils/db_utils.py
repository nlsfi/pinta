# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

import sqlmodel

from pinta_db_utils import engine_utils

_CREATE_DB_LOCK_KEY = "pinta-create-db"


def _create_from_template(db_name: str, template_name: str) -> None:
    kill_connections_query = sqlmodel.text(
        "SELECT pg_terminate_backend(pg_stat_activity.pid) "
        "FROM pg_stat_activity "
        "WHERE pg_stat_activity.datname = :db_name "
        "AND pid <> pg_backend_pid()"
    )

    with engine_utils.get_autocommit_connection(
        get_admin_credentials("postgres")
    ) as connection:
        # To avoid race conditions with pytest-xdist
        connection.execute(
            sqlmodel.text("SELECT pg_advisory_lock(hashtext(:key))"),
            {"key": _CREATE_DB_LOCK_KEY},
        )
        try:
            connection.execute(kill_connections_query, {"db_name": db_name})
            connection.execute(kill_connections_query, {"db_name": template_name})
            connection.execute(sqlmodel.text(f"DROP DATABASE IF EXISTS {db_name}"))
            connection.execute(
                sqlmodel.text(
                    f"CREATE DATABASE {db_name} WITH TEMPLATE {template_name}"
                )
            )
        finally:
            connection.execute(
                sqlmodel.text("SELECT pg_advisory_unlock(hashtext(:key))"),
                {"key": _CREATE_DB_LOCK_KEY},
            )


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


def get_processing_worker_credentials(
    db_name: str,
) -> engine_utils.Credentials:
    """Get connection parameters for the db."""
    return engine_utils.Credentials(
        os.environ["DB_PROCESSING_WORKER_USER"],
        os.environ["DB_PROCESSING_WORKER_PASSWORD"],
        os.environ["DB_HOST"],
        os.environ["DB_PORT"],
        db_name,
    )


def create_db(worker_id: str) -> str:
    """Create a new database for the test session."""
    db_name = os.environ["DB_NAME"] + f"_test_{worker_id}"
    _create_from_template(db_name, os.environ["DB_NAME"])
    return db_name


def create_job_db(worker_id: str) -> str:
    """Create a new database for the test session."""
    db_name = f"test_job_{worker_id}"
    _create_from_template(db_name, os.environ["DB_JOB_TEMPLATE_NAME"])
    return db_name
