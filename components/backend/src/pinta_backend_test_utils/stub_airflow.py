# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import uuid
from typing import Annotated, Any, TypedDict

import fastapi
from pinta_common import constants

STUB_BEARER_TOKEN = "stub-token"  # noqa: S105
STUB_AIRFLOW_USERNAME = "pinta-backend"
STUB_AIRFLOW_PASSWORD = "stub-password"  # noqa: S105

HELLO_WORLD_DAG_ID = constants.DAG_ID_HELLO_WORLD
HELLO_WORLD_TAG = constants.DAG_ID_HELLO_WORLD


class StubAirflowState(TypedDict):
    """Captured requests against the stub Airflow API."""

    token_requests: list[dict[str, Any]]
    trigger_requests: list[dict[str, Any]]


def _require_bearer(request: fastapi.Request) -> None:
    if request.headers.get("Authorization") != f"Bearer {STUB_BEARER_TOKEN}":
        raise fastapi.HTTPException(status_code=401, detail="Unauthorized")


def build_stub_airflow() -> tuple[fastapi.FastAPI, StubAirflowState]:
    """Return a FastAPI app that fakes the Airflow REST endpoints we use."""
    state: StubAirflowState = {"token_requests": [], "trigger_requests": []}
    stub = fastapi.FastAPI()
    bearer_required = [fastapi.Depends(_require_bearer)]

    @stub.post("/auth/token")
    async def issue_token(payload: dict[str, Any]) -> dict[str, str]:
        state["token_requests"].append(payload)
        return {"access_token": STUB_BEARER_TOKEN}

    @stub.get("/api/v2/dags", dependencies=bearer_required)
    async def list_dags(
        tags: Annotated[list[str] | None, fastapi.Query()] = None,
        tags_match_mode: str | None = None,  # noqa: ARG001
    ) -> dict[str, Any]:
        if not tags or HELLO_WORLD_TAG not in tags:
            return {"dags": [], "total_entries": 0}
        return {
            "dags": [
                {
                    "dag_id": HELLO_WORLD_DAG_ID,
                    "dag_display_name": "Print hello world",
                    "file_token": "tok",
                    "fileloc": "/dags/print_hello_world.py",
                    "has_import_errors": False,
                    "has_task_concurrency_limits": False,
                    "is_paused": False,
                    "is_stale": False,
                    "max_active_tasks": 16,
                    "max_consecutive_failed_dag_runs": 0,
                    "owners": ["airflow"],
                    "tags": [
                        {
                            "name": HELLO_WORLD_TAG,
                            "dag_id": HELLO_WORLD_DAG_ID,
                            "dag_display_name": "Print hello world",
                        }
                    ],
                    "timetable_partitioned": False,
                }
            ],
            "total_entries": 1,
        }

    @stub.get("/api/v2/dags/{dag_id}/details", dependencies=bearer_required)
    async def get_dag_details(dag_id: str) -> dict[str, Any]:
        if dag_id != HELLO_WORLD_DAG_ID:
            raise fastapi.HTTPException(status_code=404, detail="Not found")
        return {
            "dag_id": dag_id,
            "dag_display_name": "Print hello world",
            "file_token": "tok",
            "fileloc": "/dags/print_hello_world.py",
            "has_import_errors": False,
            "has_task_concurrency_limits": False,
            "is_paused": False,
            "is_stale": False,
            "max_active_tasks": 16,
            "max_consecutive_failed_dag_runs": 0,
            "owners": ["airflow"],
            "tags": [
                {
                    "name": HELLO_WORLD_TAG,
                    "dag_id": HELLO_WORLD_DAG_ID,
                    "dag_display_name": "Print hello world",
                }
            ],
            "catchup": False,
            "concurrency": 16,
            "render_template_as_native_obj": False,
            "params": {
                "name": {
                    "__class": "airflow.sdk.definitions.param.Param",
                    "value": "World",
                    "description": "Name to greet in the log line.",
                    "schema": {"type": "string"},
                },
            },
        }

    @stub.post("/api/v2/dags/{dag_id}/dagRuns", dependencies=bearer_required)
    async def trigger_dag_run(
        dag_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        state["trigger_requests"].append({"dag_id": dag_id, "payload": payload})
        return {
            "dag_id": dag_id,
            "dag_display_name": "Print hello world",
            "dag_run_id": f"manual__{uuid.uuid4()}",
            "dag_versions": [],
            "logical_date": None,
            "run_after": "2026-05-25T00:00:00Z",
            "run_type": "manual",
            "state": "queued",
        }

    return stub, state
