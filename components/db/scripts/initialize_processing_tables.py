# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Materialize the canonical `processing` schema staging raster tables.

Meant to be run by CI for maintaining documentation.
"""

import logging
import os

import dotenv
import sqlalchemy as sa
import sqlmodel

dotenv.load_dotenv()

from pinta_db_test_utils import db_utils  # noqa: E402
from pinta_db_utils.postgis import raster  # noqa: E402

logger = logging.getLogger(__name__)

_SCHEMA = "processing"
_TABLE = "dem"


def main() -> None:
    """Create canonical processing-schema raster staging tables if missing."""
    credentials = db_utils.get_primary_processing_worker_credentials(
        os.environ["DB_PRIMARY_NAME"]
    )
    engine = sa.create_engine(credentials.get_connection_string())
    try:
        with sqlmodel.Session(engine) as session:
            inspector = sa.inspect(engine)

            if not inspector.has_table(_TABLE, schema=_SCHEMA):
                msg = (
                    f"{_SCHEMA}.{_TABLE} is missing; main raster tables must "
                    "come from the template database"
                )
                raise SystemExit(msg)

            overview_names = [
                raster.OVERVIEW_TABLE_NAME.format(level=level, table_name=_TABLE)
                for level in raster.DEFAULT_OVERVIEW_LEVELS
            ]
            missing = [
                name
                for name in overview_names
                if not inspector.has_table(name, schema=_SCHEMA)
            ]
            if missing:
                msg = (
                    f"overview tables missing in {_SCHEMA} ({missing}); main "
                    "overview tables must come from the template database"
                )
                raise SystemExit(msg)

            raster.initialize_raster_table(session, _SCHEMA, _TABLE)
            logger.info("initialized staging tables for %s.%s", _SCHEMA, _TABLE)

            raster.initialize_overview_tables(session, _SCHEMA, _TABLE)
            for level in raster.DEFAULT_OVERVIEW_LEVELS:
                overview_name = raster.OVERVIEW_TABLE_NAME.format(
                    level=level, table_name=_TABLE
                )
                raster.register_overview_table(
                    session, _SCHEMA, _TABLE, overview_name, level
                )
                raster.create_raster_index(session, _SCHEMA, overview_name)
            session.commit()
            logger.info("initialized overview staging tables in %s", _SCHEMA)
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
