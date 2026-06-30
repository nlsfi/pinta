# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

from pinta_common import exceptions

TRUTHY_STRINGS = ("1", "true", "yes", "t")


def _require(name: str) -> str:
    """Return the environment variable `name` or raise if it is unset."""
    try:
        return os.environ[name]
    except KeyError:
        raise exceptions.MissingEnvironmentError(name) from None


def _is_truthy(value: str) -> bool:
    """Check if the env variable represents a truthy value."""
    return value.lower() in TRUTHY_STRINGS


class _Settings:
    """Pinta shared runtime configuration read from the environment.

    Each value is read from the environment on access rather than at import
    time.
    """

    @property
    def DB_SRID(self) -> str:  # noqa: N802
        return _require("DB_SRID")

    @property
    def DB_DEM_PIXEL_SIZE(self) -> int:  # noqa: N802
        return int(_require("DB_DEM_PIXEL_SIZE"))

    @property
    def DB_DEM_NODATA(self) -> float:  # noqa: N802
        return float(_require("DB_DEM_NODATA"))

    @property
    def DB_DEFAULT_TILE_SIZE(self) -> int:  # noqa: N802
        return int(os.environ.get("DB_DEFAULT_TILE_SIZE", "256"))

    @property
    def DB_JOB_TEMPLATE_NAME(self) -> str:  # noqa: N802
        return os.environ.get("DB_JOB_TEMPLATE_NAME", "job_template")

    @property
    def LASTOOLS_DEMO_MODE(self) -> bool:  # noqa: N802
        # When set to a truthy value, LASTools commands are invoked with `-demo`.
        return _is_truthy(os.environ.get("LASTOOLS_DEMO_MODE", ""))


Settings = _Settings()
