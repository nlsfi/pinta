# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Initial schemas and roles

Revision ID: 001
Revises:
Create Date: 2026-04-27 11:56:04.970196

"""

import os
from collections.abc import Sequence

from migrations import _schema_op as schema_op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = os.environ["DB_OWNER_ROLE"]
WRITER = os.environ["DB_WRITER_ROLE"]
READER = os.environ["DB_READER_ROLE"]
PROCESSING_WORKER = os.environ["DB_PROCESSING_WORKER_ROLE"]

MANAGEMENT_SCHEMA = "management"
PROCESSING_SCHEMA = "processing"
DEM_SCHEMA = "dem"


def upgrade() -> None:
    """Upgrade schema."""
    # Create roles
    # Owner role has to be created before running this migration
    schema_op.create_role(WRITER)
    schema_op.create_role(READER)
    schema_op.create_role(PROCESSING_WORKER)

    # Management schema
    schema_op.create_schema(MANAGEMENT_SCHEMA, OWNER)

    schema_op.grant_privileges_on_schema(
        schema=MANAGEMENT_SCHEMA, role=WRITER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=MANAGEMENT_SCHEMA,
        schema_owner=OWNER,
        role=WRITER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    schema_op.grant_privileges_on_schema(
        schema=MANAGEMENT_SCHEMA, role=READER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=MANAGEMENT_SCHEMA,
        schema_owner=OWNER,
        role=READER,
        privileges=("SELECT",),
    )

    schema_op.grant_privileges_on_schema(
        schema=MANAGEMENT_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=MANAGEMENT_SCHEMA,
        schema_owner=PROCESSING_WORKER,
        role=READER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    # Processing schema
    schema_op.create_schema(PROCESSING_SCHEMA, OWNER)

    schema_op.grant_privileges_on_schema(
        schema=PROCESSING_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE", "CREATE")
    )

    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=PROCESSING_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=PROCESSING_SCHEMA,
        schema_owner=PROCESSING_WORKER,
        role=OWNER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
        grant_option=True,
    )

    # DEM schema
    schema_op.create_schema(DEM_SCHEMA, OWNER)

    schema_op.grant_privileges_on_schema(
        schema=DEM_SCHEMA, role=WRITER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=DEM_SCHEMA,
        schema_owner=OWNER,
        role=WRITER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    schema_op.grant_privileges_on_schema(
        schema=DEM_SCHEMA, role=READER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=DEM_SCHEMA, schema_owner=OWNER, role=READER, privileges=("SELECT",)
    )


def downgrade() -> None:
    """Downgrade schema."""
    schema_op.drop_schema(DEM_SCHEMA)
    schema_op.drop_schema(PROCESSING_SCHEMA)
    schema_op.drop_schema(MANAGEMENT_SCHEMA)
    schema_op.drop_role(PROCESSING_WORKER)
    schema_op.drop_role(READER)
    schema_op.drop_role(WRITER)
    # Owner role is not dropped
