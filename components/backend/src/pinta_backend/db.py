# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import typing

import sqlalchemy
import sqlalchemy.exc
import sqlmodel

from pinta_backend import settings


def check_primary_db() -> None:
    """Raise if the primary database is not reachable (executes SELECT 1)."""
    current_settings = settings.get_settings()
    engine = sqlalchemy.create_engine(current_settings.primary_db_uri)
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
    finally:
        engine.dispose()


@contextlib.contextmanager
def primary_db_session(
    db_name: str | None = None,
) -> typing.Generator[sqlmodel.Session, typing.Any, None]:
    """Create a new primary database session, optionally targeting `db_name`."""
    current_settings = settings.get_settings()
    uri = (
        current_settings.primary_db_uri
        if db_name is None
        else current_settings.primary_db_uri_for(db_name)
    )
    engine = sqlalchemy.create_engine(uri)
    try:
        with sqlmodel.Session(engine) as session:
            yield session
    finally:
        engine.dispose()
