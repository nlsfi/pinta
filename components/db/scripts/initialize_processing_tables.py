# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Materialize the canonical `processing` schema raster tables.

Meant to be run by CI for maintaining documentation.
"""

import logging
import os

import dotenv
import sqlalchemy as sa
import sqlmodel

dotenv.load_dotenv()

from pinta_db.primary_db.schema import Schema  # noqa: E402
from pinta_db_test_utils import db_utils  # noqa: E402
from pinta_db_utils.postgis import raster  # noqa: E402

logger = logging.getLogger(__name__)

_SCHEMA = Schema.PROCESSING.value
_TABLE = "dem"


def _exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name, schema=_SCHEMA)


def main() -> None:
    """Create the canonical processing-schema raster tables if missing."""
    credentials = db_utils.get_primary_processing_worker_credentials(
        os.environ["DB_PRIMARY_NAME"]
    )
    engine = sa.create_engine(credentials.get_connection_string())
    try:
        with sqlmodel.Session(engine) as session:
            inspector = sa.inspect(engine)

            if _exists(inspector, _TABLE):
                logger.info("%s.%s already exists, skipping", _SCHEMA, _TABLE)
            else:
                raster.initialize_raster_table(session, _SCHEMA, _TABLE)
                logger.info("created %s.%s", _SCHEMA, _TABLE)

            inspector = sa.inspect(engine)
            overview_names = [
                raster.OVERVIEW_TABLE_NAME.format(level=level, table_name=_TABLE)
                for level in raster.DEFAULT_OVERVIEW_LEVELS
            ]
            existing = [name for name in overview_names if _exists(inspector, name)]
            if len(existing) == len(overview_names):
                logger.info(
                    "all overview tables in %s already exist, skipping", _SCHEMA
                )
            elif existing:
                msg = (
                    f"partial overview tables present in {_SCHEMA} ({existing}); "
                    "drop them manually before re-running"
                )
                raise SystemExit(msg)
            else:
                raster.initialize_overview_tables(session, _SCHEMA, _TABLE)
                session.commit()
                logger.info("created overview tables in %s", _SCHEMA)
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
