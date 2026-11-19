# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Add update area dirty trigger

Revision ID: 011
Revises: 010
Create Date: 2026-07-03

"""

import os
import textwrap
from collections.abc import Sequence

from alembic import op
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str | Sequence[str] | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USER_SCHEMA = "user_data"
_UPDATE_AREA = f"{_USER_SCHEMA}.update_area"
_PROCESSING_WORKER_ROLE = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]

_set_update_area_dirty = PGFunction(
    schema=_USER_SCHEMA,
    signature="set_update_area_dirty()",
    definition=textwrap.dedent(
        f"""\
        RETURNS trigger AS $$
        BEGIN
            IF NOT pg_has_role(
                current_user, '{_PROCESSING_WORKER_ROLE}', 'MEMBER'
            ) THEN
                NEW.dirty := true;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE 'plpgsql';
        """
    ),
)

_set_update_area_dirty_trigger = PGTrigger(
    schema=_USER_SCHEMA,
    signature="set_update_area_dirty_trigger",
    on_entity=_UPDATE_AREA,
    is_constraint=False,
    definition=f"""
    BEFORE UPDATE ON {_UPDATE_AREA}
    FOR EACH ROW EXECUTE FUNCTION
    {_USER_SCHEMA}.set_update_area_dirty()
    """,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_entity(_set_update_area_dirty)
    op.create_entity(_set_update_area_dirty_trigger)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_entity(_set_update_area_dirty_trigger)
    op.drop_entity(_set_update_area_dirty)
