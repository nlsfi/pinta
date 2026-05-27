# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Authenticated HTTP wrapper for the Airflow REST API used by e2e tests."""

import datetime
import time
from http import HTTPStatus
from typing import Any, Self

import requests

DAG_RUN_TERMINAL_STATES = frozenset({"success", "failed"})
DEFAULT_HTTP_TIMEOUT_S = 10.0
DEFAULT_POLL_INTERVAL_S = 1.0


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

    # ---- DAG runs --------------------------------------------------------

    def trigger_dag_run(
        self, dag_id: str, *, conf: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Trigger a manual run of dag_id and return the parsed response body."""
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
        return response.json()

    def get_dag_run(self, dag_id: str, dag_run_id: str) -> dict[str, Any]:
        """Fetch the parsed state of a single DAG run."""
        response = requests.get(
            f"{self.base_url}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()

    def wait_for_dag_run(
        self,
        dag_id: str,
        dag_run_id: str,
        *,
        timeout: float = 180.0,
        interval: float = DEFAULT_POLL_INTERVAL_S,
    ) -> str:
        """Poll a DAG run until it reaches a terminal state, returning that state."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.get_dag_run(dag_id, dag_run_id).get("state")
            if state in DAG_RUN_TERMINAL_STATES:
                return state
            time.sleep(interval)
        msg = (
            f"DAG run {dag_id}/{dag_run_id} did not reach a terminal state "
            f"within {timeout}s"
        )
        raise TimeoutError(msg)

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

    def get_connection(self, conn_id: str) -> dict[str, Any]:
        """Fetch an Airflow connection definition."""
        response = requests.get(
            f"{self.base_url}/api/v2/connections/{conn_id}",
            headers=self._headers,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()

    def patch_connection(
        self, conn_id: str, *, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH a subset of fields on an Airflow connection.

        The Airflow API requires connection_id and conn_type in the
        request body even when update_mask is used, so we fetch the current
        connection and merge the requested fields on top.
        """
        current = self.get_connection(conn_id)
        body = {**current, **fields}
        response = requests.patch(
            f"{self.base_url}/api/v2/connections/{conn_id}",
            headers=self._headers,
            params={"update_mask": list(fields.keys())},
            json=body,
            timeout=DEFAULT_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.json()
