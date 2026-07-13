# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_trigger import PGTrigger

from pinta_db.job_db import functions, triggers
from pinta_db.job_db.schema import Schema


def test_set_update_area_dirty_function_definition() -> None:
    function = functions.set_update_area_dirty

    assert isinstance(function, PGFunction)
    assert function.schema == Schema.USER.value
    assert function.signature == "set_update_area_dirty()"
    # Only non-worker edits flip the flag; the worker's own clears are left alone.
    assert os.environ["DB_JOB_PROCESSING_WORKER_ROLE"] in function.definition
    assert "pg_has_role" in function.definition
    assert "NEW.dirty := true" in function.definition
    assert [function] == functions.ALL


def test_set_update_area_dirty_trigger_definition() -> None:
    trigger = triggers.trigger_set_update_area_dirty

    assert isinstance(trigger, PGTrigger)
    assert trigger.schema == Schema.USER.value
    assert trigger.signature == "set_update_area_dirty_trigger"
    assert trigger.on_entity == f"{Schema.USER.value}.update_area"
    assert "BEFORE UPDATE" in trigger.definition
    # The trigger wires the update area table to the dirty-flag function.
    assert functions.set_update_area_dirty.signature in trigger.definition
    assert [trigger] == triggers.ALL
