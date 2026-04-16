# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""All the models of the database.

This module should import all the models so that
Alembic can find those to autogenerate migrations.
"""

from pinta_db.main_db.models.dem import *  # noqa: F403
from pinta_db.main_db.models.management import *  # noqa: F403  # noqa: F403
