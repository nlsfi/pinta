# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from sqlmodel import SQLModel

from pinta_db_utils import model_utils


def foreign_key(model_class: type[SQLModel], field_name: str = "id") -> str:
    """Generate foreign key string representation."""
    schema, table = model_utils.schema_and_table(model_class)
    return f"{schema}.{table}.{field_name}"
