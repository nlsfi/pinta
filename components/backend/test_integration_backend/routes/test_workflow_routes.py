# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import httpx

from pinta_backend_test_utils import (
    STUB_AIRFLOW_PASSWORD,
    STUB_AIRFLOW_USERNAME,
    StubAirflowState,
)


def test_integration_trigger_workflow_against_stub_airflow(
    backend_with_stub_airflow: str,
    stub_airflow: tuple[str, StubAirflowState],
) -> None:
    _, state = stub_airflow
    state["token_requests"].clear()
    state["trigger_requests"].clear()

    response = httpx.post(
        f"{backend_with_stub_airflow}/workflows/hello_world",
        json={"parameters": {"name": "Pinta"}},
        timeout=10,
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["dag_id"] == "print_hello_world"
    assert body["dag_run_id"].startswith("manual__")
    assert body["message"]

    assert state["token_requests"] == [
        {"username": STUB_AIRFLOW_USERNAME, "password": STUB_AIRFLOW_PASSWORD}
    ]
    assert len(state["trigger_requests"]) == 1
    triggered = state["trigger_requests"][0]
    assert triggered["dag_id"] == "print_hello_world"
    assert triggered["payload"]["conf"] == {"name": "Pinta"}


def test_integration_rejects_wrong_param_type_before_trigger(
    backend_with_stub_airflow: str,
    stub_airflow: tuple[str, StubAirflowState],
) -> None:
    _, state = stub_airflow
    state["trigger_requests"].clear()

    response = httpx.post(
        f"{backend_with_stub_airflow}/workflows/hello_world",
        json={"parameters": {"name": 42}},
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "name" in response.json()["detail"]
    # Validation runs before any trigger — Airflow should not see this request.
    assert state["trigger_requests"] == []
