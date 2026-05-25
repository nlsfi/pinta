# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import types
from typing import Any
from unittest import mock

import pytest
from fastapi import testclient

from pinta_backend import exceptions


def _dag_run(dag_id: str = "print_hello_world", run_id: str = "manual__1") -> Any:
    return types.SimpleNamespace(dag_id=dag_id, dag_run_id=run_id)


def test_trigger_workflow_returns_dag_run_on_success(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
) -> None:
    mock_airflow_client.trigger_dag_by_tag.return_value = _dag_run()

    response = client_with_mock_airflow.post("/workflows/hello")

    assert response.status_code == 202
    body = response.json()
    assert body["dag_id"] == "print_hello_world"
    assert body["dag_run_id"] == "manual__1"
    assert body["message"]
    mock_airflow_client.trigger_dag_by_tag.assert_awaited_once_with("hello", conf=None)


def test_trigger_workflow_forwards_parameters_payload(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
) -> None:
    mock_airflow_client.trigger_dag_by_tag.return_value = _dag_run()

    response = client_with_mock_airflow.post(
        "/workflows/hello",
        json={"parameters": {"folder": "/input/dem", "limit": 5}},
    )

    assert response.status_code == 202
    mock_airflow_client.trigger_dag_by_tag.assert_awaited_once_with(
        "hello", conf={"folder": "/input/dem", "limit": 5}
    )


def test_trigger_workflow_accepts_empty_body(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
) -> None:
    mock_airflow_client.trigger_dag_by_tag.return_value = _dag_run()

    response = client_with_mock_airflow.post("/workflows/hello", json={})

    assert response.status_code == 202
    mock_airflow_client.trigger_dag_by_tag.assert_awaited_once_with("hello", conf=None)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (exceptions.InvalidWorkflowParametersError("'folder' is required"), 400),
        (exceptions.DagNotFoundForTagError("missing"), 404),
        (exceptions.MultipleDagsForTagError("dup", ["a", "b"]), 500),
        (exceptions.AirflowAuthError("bad creds"), 502),
        (exceptions.AirflowUnreachableError("dns"), 502),
        (exceptions.AirflowApiError(500, "boom"), 502),
    ],
)
def test_trigger_workflow_maps_client_errors_to_http_errors(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    exc: Exception,
    expected_status: int,
) -> None:
    mock_airflow_client.trigger_dag_by_tag.side_effect = exc

    response = client_with_mock_airflow.post("/workflows/some-tag")

    assert response.status_code == expected_status
    assert response.json()["detail"]
