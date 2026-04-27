# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Module to confugre Alembic migrations.

env.py module is used to configure, create and run database
 migrations for a certain database.

If there is need to set up multiple different databases,
make separate migration folders for each.
"""

import logging.config
import os

import alembic
import dotenv

# Get env variables before importing models
dotenv.load_dotenv()

from migrations import common  # noqa: E402
from pinta_db.common.base import BaseJobDb  # noqa: E402
from pinta_db.job_db import schema  # noqa: E402
from pinta_db.job_db.models.all import *  # noqa: F403, E402
from pinta_db_utils import engine_utils  # noqa: E402

config = alembic.context.config

if config.config_file_name is not None:
    logging.config.fileConfig(config.config_file_name)

target_metadata = BaseJobDb.metadata

ADMIN_CREDENTIALS = engine_utils.Credentials(
    user=os.environ["DB_ADMIN_USER"],
    password=os.environ["DB_ADMIN_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    db_name=os.environ["DB_JOB_TEMPLATE_NAME"],
    role=os.environ["DB_OWNER_ROLE"],
)

config.set_main_option("sqlalchemy.url", ADMIN_CREDENTIALS.get_connection_string())

common.run_migrations_online(
    config=config,
    target_metadata=target_metadata,
    migration_schema=schema.Schema.MIGRATION.value,
)
