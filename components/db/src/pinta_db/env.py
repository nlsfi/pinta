# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

from pinta_db.exceptions import MissingEnvironmentError

try:
    SRID = os.environ["DB_SRID"]
except KeyError as e:
    raise MissingEnvironmentError(e.args[0]) from None
