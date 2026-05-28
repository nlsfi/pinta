# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Authenticated HTTP wrapper for the Airflow REST API used by e2e tests."""

import datetime
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Self

import requests

DAG_RUN_TERMINAL_STATES = frozenset({"success", "failed"})
DEFAULT_HTTP_TIMEOUT_S = 10.0
DEFAULT_POLL_INTERVAL_S = 1.0


@dataclass(frozen=True)
class DagRun:
    """A single Airflow DAG run."""

    id: str
    run_id: str
    state: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "DagRun":
        """Build a DagRun from an Airflow API or backend response."""
        return cls(
            id=data["dag_id"],
            run_id=data["dag_run_id"],
            state=data.get("state", "success"),
        )


@dataclass(frozen=True)
class TaskInstance:
    """A single task instance within a DAG run."""

    task_id: str
    state: str | None = None
    try_number: int = 1
    map_index: int = -1

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TaskInstance":
        """Build a TaskInstance from an Airflow API task-instance object."""
        return cls(
            task_id=data["task_id"],
            state=data.get("state"),
            try_number=data.get("try_number") or 1,
            map_index=data.get("map_index", -1),
        )


@dataclass(frozen=True)
class Connection:
    """An Airflow connection definition."""

    conn_id: str
    conn_type: str | None = None
    host: str | None = None
    login: str | None = None
    schema: str | None = None
    port: int | None = None
    description: str | None = None
    extra: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Connection":
        """Build a Connection from an Airflow API connection object."""
        return cls(
            conn_id=data.get("connection_id", ""),
            conn_type=data.get("conn_type"),
            host=data.get("host"),
            login=data.get("login"),
            schema=data.get("schema"),
            port=data.get("port"),
            description=data.get("description"),
            extra=data.get("extra"),
        )


def _render_log_content(content: object) -> str:
    """Flatten Airflow's structured log content into readable lines."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    lines = []
    for entry in content:
        if not isinstance(entry, dict):
            lines.append(str(entry))
            continue
        event = str(entry.get("event", ""))
        if event.startswith("::"):  # ::group:: / ::endgroup:: markers
            continue
        prefix = " ".join(
            part for part in (entry.get("timestamp"), entry.get("level")) if part
        )
        lines.append(f"{prefix} {event}".strip())
    return "\n".join(lines)


class AirflowClient:
    """Authenticated client bound to a token for one Airflow API base URL."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def login(cls, base_url: str, username: str, password: str) -> Self:
        """Exchange username/password for a token and return a client."""
        response = requests.post(
            f"{base_url.rstrip('/')}/auth/token",
            json={"username": username, "password": password},
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return cls(base_url=base_url, token=response.json()["access_token"])

    def trigger_dag_run(
        self, dag_id: str, *, conf: dict[str, Any] | None = None
    ) -> DagRun:
        """Trigger a manual run of dag_id and return the created run."""
        body: dict[str, Any] = {
            "logical_date": datetime.datetime.now(tz=datetime.UTC).isoformat(),  # noqa: SC200
        }
        if conf is not None:
            body["conf"] = conf
        response = requests.post(
            f"{self.base_url}/api/v2/dags/{dag_id}/dagRuns",
            headers=self._headers,
            json=body,
            timeout=DEFAULT_HTTP_TIMEOUT_S * 3,
        )
        response.raise_for_status()
        data = response.json()
        return DagRun.from_api(data)

    def get_dag_run(self, dag_run: DagRun) -> DagRun:
        """Fetch a single DAG run."""
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_run.id}/dagRuns/{dag_run.run_id}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return DagRun(
            id=dag_run.id, run_id=dag_run.run_id, state=response.json().get("state")
        )

    def wait_for_dag_run(
        self,
        dag_run: DagRun,
        *,
        timeout: float = 180.0,
        interval: float = DEFAULT_POLL_INTERVAL_S,
    ) -> str:
        """Poll a DAG run until it reaches a terminal state, returning that state."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.get_dag_run(dag_run).state
            if state is not None and state in DAG_RUN_TERMINAL_STATES:
                return state
            time.sleep(interval)
        msg = (
            f"DAG run {dag_run.id}/{dag_run.run_id} did not reach a terminal state "
            f"within {timeout}s"
        )
        raise TimeoutError(msg)

    def get_task_instances(self, dag_run: DagRun) -> list[TaskInstance]:
        """List the task instances of a DAG run."""
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_run.id}/dagRuns/{dag_run.run_id}/taskInstances",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return [
            TaskInstance.from_api(task)
            for task in response.json().get("task_instances", [])
        ]

    def get_task_log(
        self,
        dag_run: DagRun,
        task_id: str,
        try_number: int,
        *,
        map_index: int = -1,
    ) -> str:
        """Fetch and render a single task instance try's log as text."""
        params: dict[str, Any] = {}
        if map_index >= 0:
            params["map_index"] = map_index
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_run.id}/dagRuns/{dag_run.run_id}/taskInstances/{task_id}/logs/{try_number}",
            headers=self._headers,
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT_S * 3,
        )
        response.raise_for_status()
        return _render_log_content(response.json().get("content", []))

    def describe_failed_run(self, dag: DagRun, *, max_log_chars: int = 6000) -> str:
        """Summarize a DAG run's task states and dump the failed tasks' logs."""
        try:
            task_instances = self.get_task_instances(dag)
        except requests.RequestException as error:
            return f"<could not fetch task instances: {error}>"

        summary = ", ".join(f"{task.task_id}={task.state}" for task in task_instances)
        sections = [f"task states: {summary}"]
        for task in task_instances:
            if task.state != "failed":
                continue
            try:
                log = self.get_task_log(
                    dag,
                    task.task_id,
                    task.try_number,
                    map_index=task.map_index,
                )
            except requests.RequestException as error:
                log = f"<could not fetch log: {error}>"
            if len(log) > max_log_chars:
                log = "...(truncated)...\n" + log[-max_log_chars:]
            sections.append(
                f"----- {task.task_id} (try {task.try_number}) log -----\n{log}"
            )
        return "\n".join(sections)

    def delete_variable(self, variable_key: str) -> None:
        """Delete an Airflow Variable; succeed silently if it doesn't exist."""
        response = requests.delete(
            f"{self.base_url}/api/v2/variables/{variable_key}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        if response.status_code not in (
            HTTPStatus.OK,
            HTTPStatus.NO_CONTENT,
            HTTPStatus.NOT_FOUND,
        ):
            response.raise_for_status()

    def get_variable_value(self, variable_key: str) -> str | None:
        """Return an Airflow Variable's string value, or None if absent."""
        response = requests.get(
            f"{self.base_url}/api/v2/variables/{variable_key}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json().get("value")

    def _get_connection_data(self, conn_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/v2/connections/{conn_id}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()

    def get_connection(self, conn_id: str) -> Connection:
        """Fetch an Airflow connection definition."""
        return Connection.from_api(self._get_connection_data(conn_id))

    def patch_connection(self, conn_id: str, *, fields: dict[str, Any]) -> Connection:
        """PATCH a subset of fields on an Airflow connection.

        The Airflow API requires connection_id and conn_type in the
        request body even when update_mask is used, so we fetch the current
        connection and merge the requested fields on top.
        """
        body = {**self._get_connection_data(conn_id), **fields}
        response = requests.patch(
            f"{self.base_url}/api/v2/connections/{conn_id}",
            headers=self._headers,
            params={"update_mask": list(fields.keys())},
            json=body,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return Connection.from_api(response.json())
