# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Airflow-related configurations."""

import datetime
import enum
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from airflow.sdk import Variable
from docker.types import Mount


class AirflowVariable(enum.StrEnum):
    """Names of Airflow Variables used across Pinta DAGs."""

    # Default number of retries for Pinta tasks.
    DEFAULT_TASK_RETRIES = "pinta_default_task_retries"

    # Maximum number of DEM files processed concurrently in a single load_dem run
    LOAD_DEM_MAX_PARALLEL_PIPELINES = "pinta_load_dem_max_parallel_pipelines"
    # Number of staging tables used during load_dem to reduce PostGIS write contention
    LOAD_DEM_STAGING_TABLES = "pinta_load_dem_staging_tables"

    # Maximum number of blast2dem tile pipelines running in parallel for reference DEM
    CALCULATE_REFERENCE_DEM_MAX_PARALLEL_PIPELINES = (
        "pinta_calculate_reference_dem_max_parallel_pipelines"
    )
    CALCULATE_REFERENCE_DEM_STAGING_TABLES = (
        "pinta_calculate_reference_dem_staging_tables"
    )

    # Maximum number of DEM diff tile pipelines running in parallel.
    CALCULATE_DEM_DIFF_MAX_PARALLEL_PIPELINES = (
        "pinta_calculate_dem_diff_max_parallel_pipelines"
    )
    CALCULATE_DEM_DIFF_STAGING_TABLES = "pinta_calculate_dem_diff_staging_tables"

    # Maximum number of update area dissolve pipelines running in parallel.
    DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES = (
        "pinta_dissolve_update_areas_max_parallel_pipelines"
    )

    # Maximum number of update area register pipelines running in parallel.
    REGISTER_UPDATE_AREAS_MAX_PARALLEL_PIPELINES = (
        "pinta_register_update_areas_max_parallel_pipelines"
    )

    # Vector mask sources as a JSON object of source name to GDAL/OGR data
    # source, e.g. {"lake_parts": "/input/finland.gpkg|layername=lake_part"}.
    MASK_OGR_SOURCES = "pinta_processing_mask_ogr_sources"


# How often a triggered child DAG is polled for completion.
TRIGGER_POKE_INTERVAL_SECONDS = 5


def connection_uri_template(conn_id: str) -> str:
    """Jinja template for a connection's SQLAlchemy URI with the psycopg3 driver."""
    return (
        f"{{{{ conn.{conn_id}.get_hook().get_uri() "
        f"| replace('postgresql://', 'postgresql+psycopg://') }}}}"
    )


def build_job_connection_uri(base_uri: str, database_name: str) -> str:
    """Return ``base_uri`` with its database path replaced by ``database_name``."""
    parts = urlsplit(base_uri)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            f"/{database_name}",
            parts.query,
            parts.fragment,
        )
    )


def _get_default_retries() -> int:
    var = AirflowVariable.DEFAULT_TASK_RETRIES
    retries = int(Variable.get(var, 0))
    if retries < 0:
        msg = f"{var} must be at least 0"
        raise ValueError(msg)
    return retries


PINTA_COMMON_TASK_ARGS: dict[str, Any] = {
    "retries": _get_default_retries(),
    "retry_delay": datetime.timedelta(seconds=10),
}

PINTA_CONTAINER_TASK_ARGS: dict[str, Any] = {
    "image": "{{ var.value.pinta_processing_image }}",
    "force_pull": False,
    # Cannot be templated at the moment
    "docker_url": Variable.get(
        "pinta_docker_socket_url", "unix:///var/run/docker.sock"
    ),
    "network_mode": Variable.get("pinta_container_network_mode", None),
    "environment": {
        "TASK_LOG_LEVEL": "{{ var.value.pinta_processing_task_log_level }}",
        "DB_SRID": "{{ var.value.pinta_db_srid }}",
        "DB_DEM_PIXEL_SIZE": "{{ var.value.pinta_db_dem_pixel_size }}",
        "DB_DEM_NODATA": "{{ var.value.pinta_db_dem_nodata }}",
        "LAStoolsLicenseFile": "/lastools/lastoolslicense.txt",
        # Resolved per run (empty = off); dev/e2e set it so unlicensed binaries run.
        "LASTOOLS_DEMO_MODE": "{{ var.value.get('pinta_lastools_demo_mode', '') }}",
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
            read_only=True,
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
if dem_base_path := Variable.get("pinta_dem_base_path", "/test_data/dem"):
    PINTA_CONTAINER_TASK_ARGS["mounts"].append(
        Mount(
            target="/dem",
            source=dem_base_path,
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
