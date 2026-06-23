# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Grant sequence privileges to processing worker on reference schema

Revision ID: 005
Revises: 004
Create Date: 2026-06-23

"""

import os
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | Sequence[str] | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROCESSING_WORKER = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA reference"
        f" TO {_PROCESSING_WORKER}"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        f"REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA reference"  # noqa: S608
        f" FROM {_PROCESSING_WORKER}"
    )
