# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from importlib import metadata
from typing import Any

import pydantic


class ApiHealth(pydantic.BaseModel):
    """Api health response."""

    backend_version: str = metadata.version("pinta_backend")
    parsed_language: str


class WorkflowTriggerRequest(pydantic.BaseModel):
    """Optional payload forwarded to the Airflow DAG run as ``conf``."""

    model_config = pydantic.ConfigDict(extra="forbid")

    parameters: dict[str, Any] | None = None


class WorkflowRunStarted(pydantic.BaseModel):
    """Response payload returned after a workflow run is triggered."""

    message: str
    dag_id: str
    dag_run_id: str


class ErrorResponse(pydantic.BaseModel):
    """Translated error payload."""

    message: str
