# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from unittest import mock

import pytest
from fastapi import testclient

from pinta_backend import exceptions


@pytest.mark.parametrize(
    ("accept_language", "expected_language"),
    [
        ("en", "en"),
        ("fi", "fi"),
        ("de", "en"),
    ],
)
def test_health_returns_version_and_language_from_header(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    accept_language: str,
    expected_language: str,
) -> None:

    response = client_with_mock_airflow.get(
        "/health", headers={"Accept-Language": accept_language}
    )

    assert response.status_code == 200
    mock_airflow_client.check_authentication.assert_awaited_once_with()
    response_body = response.json()
    assert response_body["backend_version"]
    assert response_body["status"] == "UP"
    assert response_body["airflow"] == {"status": "UP", "detail": None}
    assert response_body["parsed_language"] == expected_language
    assert response.headers["Content-Language"] == expected_language


@pytest.mark.parametrize(
    ("exc", "expected_detail"),
    [
        (exceptions.AirflowAuthError("bad credentials"), "bad credentials"),
        (exceptions.AirflowUnreachableError("connection failed"), "connection failed"),
        (exceptions.AirflowApiError(500, "server error"), "server error"),
    ],
)
def test_health_returns_500_when_airflow_login_fails(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    exc: Exception,
    expected_detail: str,
) -> None:
    mock_airflow_client.check_authentication.side_effect = exc

    response = client_with_mock_airflow.get("/health")

    assert response.status_code == 500
    response_body = response.json()
    assert response_body["backend_version"]
    assert response_body["status"] == "DOWN"
    assert response_body["airflow"] == {
        "status": "DOWN",
        "detail": expected_detail,
    }
    assert response_body["parsed_language"] == "en"
