# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
from collections.abc import Iterable

import sqlmodel
from sqlalchemy import bindparam

from pinta_db import constants
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


def reset_primary_db(db_name: str) -> None:
    """Empty the pinta-managed schemas of an existing primary database clone."""
    _truncate_pinta_schemas(get_primary_admin_credentials(db_name))


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
    reset_primary_db(db_name)
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


def get_job_database_names(primary_db_name: str) -> set[str]:
    """Return the job databases referenced by a primary database's areas."""
    with engine_utils.get_autocommit_connection(
        get_primary_admin_credentials(primary_db_name)
    ) as connection:
        return set(
            connection.execute(
                sqlmodel.text(
                    "SELECT database_name FROM management.production_area "
                    "WHERE database_name IS NOT NULL"
                )
            )
            .scalars()
            .all()
        )


def drop_job_databases(db_names: Iterable[str]) -> None:
    """Drop the given job databases, never the shared job template.

    Names outside the job namespace are skipped: a test may leave an area
    pointing at a database the DAGs would never provision, and dropping that
    would take out an unrelated database such as `postgres`. The template
    carries the `job_` prefix under its default name, so the prefix check
    alone does not protect it.
    """
    template_name = os.environ["DB_JOB_TEMPLATE_NAME"]
    targets = sorted(
        name
        for name in set(db_names)
        if name.startswith(constants.JOB_DATABASE_NAME_PREFIX) and name != template_name
    )
    if not targets:
        return
    with engine_utils.get_autocommit_connection(
        get_job_admin_credentials("postgres")
    ) as connection:
        for db_name in targets:
            database_utils.drop_database(connection, db_name)
