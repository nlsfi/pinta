# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from alembic_utils import pg_trigger

from pinta_db.job_db import functions
from pinta_db.job_db.models import user
from pinta_db.job_db.schema import Schema
from pinta_db_utils import model_utils

_update_area = ".".join(model_utils.schema_and_table(user.UpdateArea))

# Fire on every update area edit so a change by any non-worker role marks the row
# dirty for re-dissolving.
trigger_set_update_area_dirty = pg_trigger.PGTrigger(
    schema=Schema.USER.value,
    signature="set_update_area_dirty_trigger",
    definition=f"""
    BEFORE UPDATE ON {_update_area}
    FOR EACH ROW EXECUTE FUNCTION
    {Schema.USER.value}.{functions.set_update_area_dirty.signature}
    """,
    on_entity=_update_area,
)

ALL = [trigger_set_update_area_dirty]
