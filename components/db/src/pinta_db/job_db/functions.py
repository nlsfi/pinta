# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import textwrap

from alembic_utils import pg_function

from pinta_db.job_db import user
from pinta_db.job_db.schema import Schema
from pinta_db_utils import model_utils

# The dissolve worker clears the dirty flag once an update area has been merged
# into the preview. Any other role editing the update area must flip it back to
# dirty so the area is re-dissolved. Membership (not the exact login user) is
# checked so the group role and its member logins are all treated as the worker.
_PROCESSING_WORKER_ROLE = os.environ["DB_JOB_PROCESSING_WORKER_ROLE"]
_RESTORE_TABLE = ".".join(model_utils.schema_and_table(user.UpdateAreaRestore))

set_update_area_dirty = pg_function.PGFunction(
    schema=Schema.USER.value,
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

# A registered update area has been copied into the primary DEM and is frozen
# for every role; the row can never be modified or removed again.
prevent_registered_update_area_modification = pg_function.PGFunction(
    schema=Schema.USER.value,
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

save_dissolved_geom_on_delete = pg_function.PGFunction(
    schema=Schema.USER.value,
    signature="save_dissolved_geom_on_delete()",
    definition=textwrap.dedent(
        f"""\
        RETURNS trigger AS $$
        BEGIN
            IF OLD.dissolved_geom IS NOT NULL THEN
                INSERT INTO {_RESTORE_TABLE} (id, geom)
                VALUES (gen_random_uuid(), OLD.dissolved_geom);
            END IF;
            RETURN NULL;
        END; $$ LANGUAGE 'plpgsql' SECURITY DEFINER;
        """  # noqa: S608
    ),
)


ALL = [
    set_update_area_dirty,
    prevent_registered_update_area_modification,
    save_dissolved_geom_on_delete,
]
