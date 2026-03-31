# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Airflow-related configurations."""

from typing import Any

from airflow.sdk import Variable
from docker.types import Mount

PINTA_CONTAINER_TASK_ARGS: dict[str, Any] = {
    "image": "localhost/pinta-processing",
    # No other way to inject log level at runtime (jinja template does not work).
    # This is not the recommended way but task decorator can't be currently overridden
    # easily. See task.py file created in this commit (deleted afterwards) for
    # example if it's possible to override task decorator in later Airflow versions.
    # https://github.com/apache/airflow/issues/44779
    "environment": {
        "TASK_LOG_LEVEL": Variable.get("pinta_processing_task_log_level", "INFO"),
    },
    "tty": True,  # To be able to see the logs
    "auto_remove": "success",
}

if mount_dir := Variable.get("pinta_processing_mount_dir", None):
    PINTA_CONTAINER_TASK_ARGS["mounts"] = [
        Mount(target="/code", source=mount_dir, type="bind", read_only=True)
    ]
