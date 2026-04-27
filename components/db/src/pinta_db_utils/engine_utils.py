# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import sqlalchemy
from pydantic import dataclasses
from sqlalchemy import Connection
from sqlmodel import Session


@dataclasses.dataclass
class Credentials:
    """DB credentials."""

    user: str
    password: str
    host: str
    port: str
    db_name: str
    role: str | None = None

    def get_connection_string(self) -> str:
        """Get connection string for DB."""
        return get_connection_string(
            self.user,
            self.host,
            self.port,
            self.password,
            self.db_name,
            self.role,
        )


def get_connection_string(  # noqa: PLR0913
    user: str,
    host: str,
    port: str,
    password: str,
    db_name: str,
    role: str | None = None,
) -> str:
    """Get connection string for DB."""
    connection_string = (
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"
    )
    if role:
        connection_string += f"?options=-crole={role}"
    return connection_string


@contextmanager
def get_session(credentials: Credentials) -> Generator[Session, Any, None]:
    """Get SQLModel Session."""
    engine = sqlalchemy.create_engine(credentials.get_connection_string())
    try:
        yield Session(engine)
    finally:
        engine.dispose()


@contextmanager
def get_autocommit_connection(
    credentials: Credentials,
) -> Generator[Connection, Any, None]:
    """Get sqlalchemy Connection with autocommit isolation level."""
    engine = sqlalchemy.create_engine(credentials.get_connection_string())
    try:
        connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            yield connection
        finally:
            connection.close()
    finally:
        engine.dispose()
