# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import typing

import sqlalchemy
import sqlmodel

from pinta_backend import settings


@contextlib.contextmanager
def primary_db_session() -> typing.Generator[sqlmodel.Session, typing.Any, None]:
    """Create a new primary database session."""
    engine = sqlalchemy.create_engine(settings.get_settings().primary_db_uri)
    try:
        yield sqlmodel.Session(engine)
    finally:
        engine.dispose()
