# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_db.schemas import (
    AccessLevel,
    DelegatedAccess,
    Role,
    Schema,
    SchemaAccess,
    SchemaConfig,
)

SCHEMA_CONFIGURATIONS_MAIN = [
    SchemaConfig(
        schema=Schema.MANAGEMENT,
        access=(
            SchemaAccess(Role.WRITER, AccessLevel.READ_WRITE),
            SchemaAccess(Role.READER, AccessLevel.READ),
            SchemaAccess(Role.PROCESSING_WORKER, AccessLevel.READ_WRITE),
        ),
    ),
    SchemaConfig(
        schema=Schema.MIGRATIONS,
    ),
    SchemaConfig(
        schema=Schema.PROCESSING,
        access=(SchemaAccess(Role.PROCESSING_WORKER, AccessLevel.MANAGE),),
        delegated=(
            DelegatedAccess(
                creator=Role.PROCESSING_WORKER,
                grantee=Role.OWNER,
                level=AccessLevel.READ_WRITE,
                with_grant_option=True,
            ),
        ),
    ),
    SchemaConfig(
        schema=Schema.DEM,
        access=(
            SchemaAccess(Role.WRITER, AccessLevel.READ_WRITE),
            SchemaAccess(Role.READER, AccessLevel.READ),
        ),
    ),
]
