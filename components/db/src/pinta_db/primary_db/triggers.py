# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from alembic_utils import pg_trigger

from pinta_db.primary_db import functions
from pinta_db.primary_db.models import management
from pinta_db.primary_db.schema import Schema
from pinta_db_utils import model_utils

_production_area = ".".join(model_utils.schema_and_table(management.ProductionArea))

trigger_update_processing_timestamp = pg_trigger.PGTrigger(
    schema=Schema.MANAGEMENT.value,
    signature="update_processing_timestamp_trigger",
    definition=f"""
    BEFORE UPDATE ON {_production_area}
    FOR EACH ROW EXECUTE FUNCTION
    {Schema.MANAGEMENT.value}.{functions.update_processing_timestamp.signature}
    """,
    on_entity=_production_area,
)

ALL = [trigger_update_processing_timestamp]
