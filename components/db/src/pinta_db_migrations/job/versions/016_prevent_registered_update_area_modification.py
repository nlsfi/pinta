# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Prevent modification of registered update areas

Revision ID: 016
Revises: 015
Create Date: 2026-08-31

"""

import textwrap
from collections.abc import Sequence

from alembic import op
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: str | Sequence[str] | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USER_SCHEMA = "user_data"
_UPDATE_AREA = f"{_USER_SCHEMA}.update_area"

_prevent_registered_update_area_modification = PGFunction(
    schema=_USER_SCHEMA,
    signature="prevent_registered_update_area_modification()",
    definition=textwrap.dedent(
        """\
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'update_area % is registered and can no longer be modified',
                OLD.id;
        END; $$ LANGUAGE 'plpgsql';
        """
    ),
)

_prevent_registered_update_area_modification_trigger = PGTrigger(
    schema=_USER_SCHEMA,
    signature="prevent_registered_update_area_modification_trigger",
    on_entity=_UPDATE_AREA,
    is_constraint=False,
    definition=f"""
    BEFORE UPDATE OR DELETE ON {_UPDATE_AREA}
    FOR EACH ROW
    WHEN (OLD.registered_at IS NOT NULL)
    EXECUTE FUNCTION
    {_USER_SCHEMA}.prevent_registered_update_area_modification()
    """,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_entity(_prevent_registered_update_area_modification)
    op.create_entity(_prevent_registered_update_area_modification_trigger)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_entity(_prevent_registered_update_area_modification_trigger)
    op.drop_entity(_prevent_registered_update_area_modification)
