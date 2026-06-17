# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from enum import StrEnum
from importlib import metadata
from typing import Any

import pydantic


class HealthStatus(StrEnum):
    """Service health status."""

    UP = "UP"
    DOWN = "DOWN"


class ApiDependencyHealth(pydantic.BaseModel):
    """Health response for a dependency."""

    status: HealthStatus
    detail: str | None = None


class ApiHealth(pydantic.BaseModel):
    """Api health response."""

    backend_version: str = metadata.version("pinta_backend")
    airflow: ApiDependencyHealth
    primary_db: ApiDependencyHealth
    parsed_language: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> HealthStatus:
        """Derive overall status from all dependency healths."""
        dependencies = (self.airflow, self.primary_db)
        return (
            HealthStatus.UP
            if all(d.status == HealthStatus.UP for d in dependencies)
            else HealthStatus.DOWN
        )


class WorkflowTriggerRequest(pydantic.BaseModel):
    """Optional payload forwarded to the Airflow DAG run as ``conf``."""

    model_config = pydantic.ConfigDict(extra="forbid")

    parameters: dict[str, Any] | None = None
    production_area_id: str | None = None


class WorkflowRunStarted(pydantic.BaseModel):
    """Response payload returned after a workflow run is triggered."""

    message: str
    dag_id: str
    dag_run_id: str


class ErrorResponse(pydantic.BaseModel):
    """Translated error payload."""

    message: str
