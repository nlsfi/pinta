# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Utility functions for working with SQLModel classes."""

from sqlmodel import SQLModel

from pinta_db.exceptions import MissingSchemaError


def foreign_key(model_class: type[SQLModel], field_name: str = "id") -> str:
    """Generate foreign key string representation."""
    table_name = model_class.__tablename__
    table_args = model_class.__table_args__ or {}  # type: ignore[attr-defined]
    if not (schema := table_args.get("schema")):
        raise MissingSchemaError(model_class)

    return f"{schema}.{table_name}.{field_name}"
