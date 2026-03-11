# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pydantic.dataclasses import dataclass
from sqlalchemy import Connection, create_engine
from sqlmodel import Session


@dataclass
class Credentials:
    """DB credentials."""

    user: str
    password: str
    host: str
    port: str
    db_name: str

    def get_connection_string(self) -> str:
        """Get connection string for DB."""
        return get_connection_string(
            self.user, self.host, self.port, self.password, self.db_name
        )


def get_connection_string(
    user: str, host: str, port: str, password: str, db_name: str
) -> str:
    """Get connection string for DB."""
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


def get_session(credentials: Credentials) -> Session:
    """Get SQLModel Session.

    Use with with statement.
    """
    return Session(create_engine(credentials.get_connection_string()))


def get_autocommit_connection(credentials: Credentials) -> Connection:
    """Get sqlalchemy Connection with autocommit isolation level.

    Use with with statement.
    """
    engine = create_engine(credentials.get_connection_string())
    return engine.connect().execution_options(isolation_level="AUTOCOMMIT")
