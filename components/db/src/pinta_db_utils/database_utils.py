# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from sqlalchemy import Connection, text

from pinta_common import Settings

_CREATE_DB_LOCK_KEY = "pinta-create-db"

_KILL_CONNECTIONS = text(
    "SELECT pg_terminate_backend(pg_stat_activity.pid) "
    "FROM pg_stat_activity "
    "WHERE pg_stat_activity.datname = :db_name "
    "AND pid <> pg_backend_pid()"
)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _database_exists(connection: Connection, db_name: str) -> bool:
    result = connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
        {"db_name": db_name},
    ).first()
    return result is not None


def initialize_db_from_template(
    connection: Connection,
    db_name: str,
    template_name: str | None = None,
    *,
    replace_existing: bool = False,
) -> bool:
    """Create ``db_name`` as a clone of ``template_name``.

    ``template_name`` defaults to ``Settings.DB_JOB_TEMPLATE_NAME`` when not
    given.

    ``connection`` must use the AUTOCOMMIT isolation level, since CREATE / DROP
    DATABASE cannot run inside a transaction block. An advisory lock serialises
    concurrent callers (e.g. parallel test workers or overlapping DAG runs).

    When the database already exists and ``replace_existing`` is False it is left
    in place and False is returned. When ``replace_existing`` is True the
    existing database is dropped and recreated. Returns True when the database
    was (re)created.
    """
    if template_name is None:
        template_name = Settings.DB_JOB_TEMPLATE_NAME

    current_db = connection.execute(text("SELECT current_database()")).scalar_one()
    if current_db in (template_name, db_name):
        msg = (
            "initialize_db_from_template must run from a maintenance database "
            f"(e.g. 'postgres'), not from the template or target database "
            f"(connected to {current_db!r})."
        )
        raise ValueError(msg)

    template = _quote_identifier(template_name)
    target = _quote_identifier(db_name)

    connection.execute(
        text("SELECT pg_advisory_lock(hashtext(:key))"),
        {"key": _CREATE_DB_LOCK_KEY},
    )
    try:
        if _database_exists(connection, db_name) and not replace_existing:
            return False

        # Block new connections to the template before terminating its sessions,
        # so nothing can reconnect before the clone.
        connection.execute(
            text(f"ALTER DATABASE {template} WITH ALLOW_CONNECTIONS false")
        )
        try:
            connection.execute(_KILL_CONNECTIONS, {"db_name": db_name})
            connection.execute(_KILL_CONNECTIONS, {"db_name": template_name})
            connection.execute(text(f"DROP DATABASE IF EXISTS {target} WITH (FORCE)"))
            connection.execute(
                text(f"CREATE DATABASE {target} WITH TEMPLATE {template}")
            )
        finally:
            connection.execute(
                text(f"ALTER DATABASE {template} WITH ALLOW_CONNECTIONS true")
            )

        return True
    finally:
        connection.execute(
            text("SELECT pg_advisory_unlock(hashtext(:key))"),
            {"key": _CREATE_DB_LOCK_KEY},
        )
