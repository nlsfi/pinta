# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging

LOGGER = logging.getLogger(__name__)


def log_hello_world(log_text: str) -> None:
    """Log hello world with given text."""
    LOGGER.debug("Debug message")
    LOGGER.info("Hello world with %s", log_text)
