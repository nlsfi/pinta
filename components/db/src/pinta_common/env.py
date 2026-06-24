# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

from pinta_common import exceptions

TRUTHY_STRINGS = (
    "1",
    "true",
    "yes",
    "t",
)


def is_truthy(value: str) -> bool:
    """Check if the env variable represents a truthy value."""
    return value.lower() in TRUTHY_STRINGS


try:
    SRID = os.environ["DB_SRID"]
except KeyError as e:
    raise exceptions.MissingEnvironmentError(e.args[0]) from None

try:
    DEM_PIXEL_SIZE = int(os.environ["DB_DEM_PIXEL_SIZE"])
except KeyError as e:
    raise exceptions.MissingEnvironmentError(e.args[0]) from None

try:
    DEM_NODATA = float(os.environ["DB_DEM_NODATA"])
except KeyError as e:
    raise exceptions.MissingEnvironmentError(e.args[0]) from None

DEFAULT_TILE_SIZE = int(os.environ.get("DB_DEFAULT_TILE_SIZE", "256"))

JOB_TEMPLATE_NAME = os.environ.get("DB_JOB_TEMPLATE_NAME", "job_template")

# When set to a non-empty value, LASTools commands are invoked with `-demo`
LASTOOLS_DEMO_MODE = is_truthy(os.environ.get("LASTOOLS_DEMO_MODE", ""))
