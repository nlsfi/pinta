# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging
import os
import sys

TASK_LOG_LEVEL = "TASK_LOG_LEVEL"


def setup_airflow_task_logging() -> None:
    """Configure the root logger if used from Airflow."""
    if (log_level := os.environ.get(TASK_LOG_LEVEL)) is not None:
        # Root logger needed for Airflow
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        formatter = logging.Formatter("TASK [%(levelname)s] %(name)s %(message)s")
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        root_logger.addHandler(console_handler)
