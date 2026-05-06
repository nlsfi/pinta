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

try:
    DEM_PIXEL_SIZE = int(os.environ["DB_DEM_PIXEL_SIZE"])
except KeyError as e:
    raise MissingEnvironmentError(e.args[0]) from None

try:
    DEM_NODATA = float(os.environ["DB_DEM_NODATA"])
except KeyError as e:
    raise MissingEnvironmentError(e.args[0]) from None

DEFAULT_TILE_SIZE = 256
