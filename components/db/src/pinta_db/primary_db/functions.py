# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import textwrap

from alembic_utils import pg_function

from pinta_db.primary_db.schema import Schema

update_processing_timestamp = pg_function.PGFunction(
    schema=Schema.MANAGEMENT.value,
    signature="update_processing_timestamp()",
    definition=textwrap.dedent(
        """\
        RETURNS trigger AS $$
        BEGIN
            IF NEW.processing_status <> OLD.processing_status THEN
                NEW.processing_status_last_updated = now();
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE 'plpgsql';
        """
    ),
)


ALL = [update_processing_timestamp]
