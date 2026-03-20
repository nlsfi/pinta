# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Utility functions for working with SQLModel classes."""

from geoalchemy2 import Geometry
from sqlmodel import SQLModel

from pinta_db.exceptions import MissingSchemaError


def foreign_key(model_class: type[SQLModel], field_name: str = "id") -> str:
    """Generate foreign key string representation."""
    table_name = model_class.__tablename__
    table_args = model_class.__table_args__ or {}  # type: ignore[attr-defined]
    if not (schema := table_args.get("schema")):
        raise MissingSchemaError(model_class)

    return f"{schema}.{table_name}.{field_name}"


def geometry_type(model_class: type[SQLModel], field_name: str = "geom") -> str:
    """Get geometry type from SQLModel class."""
    field = model_class.model_fields.get(field_name)
    if (
        field is None or not hasattr(field, "sa_column") or field.sa_column is None  # type: ignore[attr-defined]
    ):
        msg = f"Geometry column '{field_name}' not found in {model_class.__name__}"
        raise ValueError(msg)
    return field.sa_column.type.geometry_type  # type: ignore[attr-defined]


def primary_key_column(model_class: type[SQLModel]) -> str:
    """Get primary key column name from SQLModel class."""
    for field_name, field_info in model_class.model_fields.items():
        if hasattr(field_info, "primary_key") and field_info.primary_key:
            return field_name

    msg = f"No primary key found in {model_class.__name__}"
    raise ValueError(msg)


def geometry_column(model_class: type[SQLModel]) -> str:
    """Get geometry column name from SQLModel class."""
    for field_name, field_info in model_class.model_fields.items():
        if not hasattr(field_info, "sa_column"):
            continue
        sa_column = field_info.sa_column  # type: ignore[attr-defined]
        if sa_column is None:
            continue
        if hasattr(sa_column, "type") and isinstance(sa_column.type, Geometry):
            return field_name

    msg = f"No geometry column found in {model_class.__name__}"
    raise ValueError(msg)
