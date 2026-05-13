# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS utility helpers."""

import sqlalchemy as sa
import sqlmodel


def session_user_owns_table(
    session: sqlmodel.Session, schema: str, table_name: str
) -> bool:
    """Return whether the current session user owns a table."""
    result = session.exec(  # type: ignore[call-overload]
        sa.text("""
            SELECT pg_get_userbyid(c.relowner) = session_user
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
            AND c.relname = :table_name
        """).bindparams(schema=schema, table_name=table_name)
    ).first()
    return bool(result and result[0])
