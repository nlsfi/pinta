# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add permissions for worker in user schema

Revision ID: 009
Revises: 008
Create Date: 2026-07-02

"""

import os
from collections.abc import Sequence

from alembic import op

from migrations import _schema_op as schema_op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | Sequence[str] | None = "008"
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
    schema_op.grant_privileges_on_schema(
        schema=USER_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE", "CREATE")
    )
    schema_op.grant_default_privileges_on_tables_in_schema(
        schema=USER_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )
    schema_op.grant_default_privileges_on_sequences_in_schema(
        schema=USER_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "USAGE"),
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA user_data"
        f" TO {PROCESSING_WORKER}"
    )


def downgrade() -> None:
    """Downgrade schema."""
    schema_op.revoke_privileges_on_schema(
        schema=USER_SCHEMA, role=PROCESSING_WORKER, privileges=("USAGE", "CREATE")
    )
    schema_op.revoke_default_privileges_on_tables_in_schema(
        schema=USER_SCHEMA,
        schema_owner=OWNER,
        role=PROCESSING_WORKER,
        privileges=("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"),
    )
    op.execute(
        f"REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA user_data"  # noqa: S608
        f" FROM {PROCESSING_WORKER}"
    )
