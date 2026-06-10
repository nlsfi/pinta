# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Airflow-related configurations."""

import datetime
from typing import Any

from airflow.sdk import Variable
from docker.types import Mount

PINTA_COMMON_TASK_ARGS: dict[str, Any] = {
    "retries": 0,  # TODO: Set to something larger in non-local environments
    "retry_delay": datetime.timedelta(seconds=10),
}

PINTA_CONTAINER_TASK_ARGS: dict[str, Any] = {
    "image": "{{ var.value.pinta_processing_image }}",
    # Cannot be templated at the moment
    "docker_url": Variable.get(
        "pinta_docker_socket_url", "unix:///var/run/docker.sock"
    ),
    "environment": {
        "TASK_LOG_LEVEL": "{{ var.value.pinta_processing_task_log_level }}",
        "DB_SRID": "{{ var.value.pinta_db_srid }}",
        "DB_DEM_PIXEL_SIZE": "{{ var.value.pinta_db_dem_pixel_size }}",
        "DB_DEM_NODATA": "{{ var.value.pinta_db_dem_nodata }}",
        "LAStoolsLicenseFile": "/lastools/lastoolslicense.txt",
    },
    "tty": True,  # To be able to see the logs
    # When using remote engine or docker-in-docker,
    # mounting temporary volume from host is not supported
    "mount_tmp_dir": False,
    "auto_remove": "success",
    "mounts": [],
    "extra_hosts": {"host.docker.internal": "host-gateway"},
}

# maybe not the most optimal way of setting mounts
if mount_dir := Variable.get("pinta_processing_code_mount_dir", None):
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target="/code",
            source=mount_dir,
            type="bind",
            read_only=True,
        )
    )
if data_dir := Variable.get("pinta_container_source_base_path", None):
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target=Variable.get("pinta_container_target_base_path", None),
            source=data_dir,
            type="bind",
            read_only=False,
        )
    )
if data_base_path := Variable.get("pinta_data_base_path", "/test_data"):
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target="/input",
            source=data_base_path,
            type="bind",
            read_only=True,
        )
    )
if lastools_path := Variable.get("pinta_lastools_path", "/external/LAStools"):
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target="/lastools",
            source=lastools_path,
            type="bind",
            read_only=True,
        )
    )
if lastools_license_path := Variable.get("pinta_lastools_license_path", None):
    PINTA_CONTAINER_TASK_ARGS["environment"]["LAStoolsLicenseFile"] = (
        "/lastoolslicense.txt"
    )
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target="/lastoolslicense.txt",
            source=lastools_license_path,
            type="bind",
            read_only=True,
        )
    )
