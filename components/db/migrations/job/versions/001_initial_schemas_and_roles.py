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

OWNER = os.environ["DB_JOB_OWNER_ROLE"]
WRITER = os.environ["DB_JOB_WRITER_ROLE"]
READER = os.environ["DB_JOB_READER_ROLE"]
PROCESSING_WORKER = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]
DB_NAME = os.environ["DB_JOB_TEMPLATE_NAME"]

REFERENCE_SCHEMA = "reference"
USER_SCHEMA = "user_data"


def upgrade() -> None:
    """Upgrade schema."""
    # Create roles
    # Owner role has to be created before running this migration
    schema_op.create_role(WRITER)
    schema_op.create_role(READER)
    schema_op.create_role(PROCESSING_WORKER)

    # Writer and processing_worker inherit reader
    schema_op.grant_role_to_role(READER, WRITER)
    schema_op.grant_role_to_role(READER, PROCESSING_WORKER)

    # Only the group roles can connect.
    schema_op.revoke_all_on_database_from_public(DB_NAME)
    schema_op.grant_database_privileges(DB_NAME, READER, ("CONNECT", "TEMP"))
    schema_op.grant_database_privileges(DB_NAME, WRITER, ("CONNECT", "TEMP"))
    schema_op.grant_database_privileges(DB_NAME, PROCESSING_WORKER, ("CONNECT", "TEMP"))

    # Reference schema
    schema_op.create_schema(REFERENCE_SCHEMA, OWNER)

    schema_op.grant_privileges_on_schema(
        schema=REFERENCE_SCHEMA, role=WRITER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=REFERENCE_SCHEMA,
        schema_owner=OWNER,
        role=WRITER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    schema_op.grant_privileges_on_schema(
        schema=REFERENCE_SCHEMA, role=READER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=REFERENCE_SCHEMA, schema_owner=OWNER, role=READER, privileges=("SELECT",)
    )

    schema_op.grant_privileges_on_schema(
        schema=REFERENCE_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=REFERENCE_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    # User schema
    schema_op.create_schema(USER_SCHEMA, OWNER)

    schema_op.grant_privileges_on_schema(
        schema=USER_SCHEMA, role=WRITER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=USER_SCHEMA,
        schema_owner=OWNER,
        role=WRITER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )

    schema_op.grant_privileges_on_schema(
        schema=USER_SCHEMA, role=READER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=USER_SCHEMA, schema_owner=OWNER, role=READER, privileges=("SELECT",)
    )

    schema_op.grant_privileges_on_schema(
        schema=USER_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE",)
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=USER_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    schema_op.drop_schema(USER_SCHEMA)
    schema_op.drop_schema(REFERENCE_SCHEMA)

    schema_op.revoke_role_from_role(READER, PROCESSING_WORKER)
    schema_op.revoke_role_from_role(READER, WRITER)

    schema_op.drop_role(PROCESSING_WORKER)
    schema_op.drop_role(READER)
    schema_op.drop_role(WRITER)
    # Owner role is not dropped
