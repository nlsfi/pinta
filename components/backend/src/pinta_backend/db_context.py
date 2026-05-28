# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import re
from contextvars import ContextVar

from pinta_backend import settings

DB_NAME_OVERRIDE_HEADER = "X-Pinta-Db-Name"
_VALID_DB_NAME = re.compile(r"[A-Za-z0-9_]+")

_db_name_override: ContextVar[str | None] = ContextVar(
    "db_name_override",
    default=None,
)


def _resolve_db_override(db_name: str | None) -> str | None:
    """Return a dev-only primary-db override if one was requested and allowed."""
    if (
        db_name is None
        or not settings.get_settings().development_mode
        or not _VALID_DB_NAME.fullmatch(db_name)
    ):
        return None
    return db_name


def set_db_name_override(db_name: str | None) -> None:
    """Store a resolved primary-db override for the current request context."""
    _db_name_override.set(_resolve_db_override(db_name))


def get_db_name_override() -> str | None:
    """Return the primary-db override for the current request context, if any."""
    return _db_name_override.get()
