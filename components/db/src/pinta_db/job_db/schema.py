# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_db.schemas import (
    AccessLevel,
    Role,
    Schema,
    SchemaAccess,
    SchemaConfig,
)

SCHEMA_CONFIGURATIONS_JOB = [
    SchemaConfig(
        schema=Schema.MIGRATIONS,
    ),
    SchemaConfig(
        schema=Schema.REFERENCE,
        access=(
            SchemaAccess(Role.WRITER, AccessLevel.READ_WRITE),
            SchemaAccess(Role.READER, AccessLevel.READ),
            SchemaAccess(Role.PROCESSING_WORKER, AccessLevel.READ_WRITE),
        ),
    ),
    SchemaConfig(
        schema=Schema.USER,
        access=(
            SchemaAccess(Role.WRITER, AccessLevel.READ_WRITE),
            SchemaAccess(Role.READER, AccessLevel.READ),
            SchemaAccess(Role.PROCESSING_WORKER, AccessLevel.READ_WRITE),
        ),
    ),
]
