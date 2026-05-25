# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging

LOGGER = logging.getLogger(__name__)


def log_hello_world(log_text: str, name: str = "World") -> None:
    """Log a greeting with the given ``name`` plus arbitrary trailing ``log_text``."""
    LOGGER.debug("Debug message")
    LOGGER.info("Hello %s with %s", name, log_text)
