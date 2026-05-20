# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging
import logging.handlers
import os
import sys

import pinta_backend


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
