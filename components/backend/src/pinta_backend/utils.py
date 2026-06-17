# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging
import logging.handlers
import os
import sys
from collections.abc import Callable

import pinta_backend
from pinta_backend import models

_LOGGER = logging.getLogger(__name__)


def check_db_health(check_fn: Callable[[], None]) -> models.ApiDependencyHealth:
    """Return UP/DOWN health for a database, calling check_fn to probe it."""
    try:
        check_fn()
        return models.ApiDependencyHealth(status=models.HealthStatus.UP)
    except Exception as e:
        detail = str(e)
        _LOGGER.exception("DB health check failed: %s", detail)
        return models.ApiDependencyHealth(
            status=models.HealthStatus.DOWN, detail=detail
        )


def setup_default_logger_handlers() -> None:
    """Setup default loggers."""
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
    pinta_backend.LOGGER.addHandler(_handler)

    if (log_file_name := os.environ.get("LOG_FILE")) is not None:
        _file_handler = logging.handlers.RotatingFileHandler(
            log_file_name, maxBytes=5 * 1000 * 1000, backupCount=5
        )
        _file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
        )
        pinta_backend.LOGGER.addHandler(_file_handler)
