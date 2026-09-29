# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import json
from pathlib import Path
from unittest import mock

import pytest
import sqlalchemy.exc
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
    assert isinstance(response_body["versions"], dict)
    assert "backend_version" not in response_body
    assert response_body["status"] == "UP"
    assert response_body["airflow"] == {"status": "UP", "detail": None}
    assert response_body["primary_db"] == {"status": "UP", "detail": None}
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
    assert isinstance(response_body["versions"], dict)
    assert response_body["status"] == "DOWN"
    assert response_body["airflow"] == {
        "status": "DOWN",
        "detail": expected_detail,
    }
    assert response_body["primary_db"] == {"status": "UP", "detail": None}
    assert response_body["parsed_language"] == "en"


def test_health_returns_500_when_db_unreachable(
    client_with_mock_airflow: testclient.TestClient,
    mock_check_primary_db: mock.MagicMock,
) -> None:
    mock_check_primary_db.side_effect = sqlalchemy.exc.OperationalError(
        "connect", {}, Exception("connection refused")
    )

    response = client_with_mock_airflow.get("/health")

    assert response.status_code == 500
    response_body = response.json()
    assert response_body["status"] == "DOWN"
    assert response_body["airflow"] == {"status": "UP", "detail": None}
    assert response_body["primary_db"]["status"] == "DOWN"
    assert response_body["primary_db"]["detail"] is not None


def test_health_returns_versions_unchanged_when_file_changes(
    client_with_mock_airflow: testclient.TestClient,
    tmp_path: Path,
) -> None:
    version_file = tmp_path / "version.json"
    versions = {
        "processing_image_tag": "latest",
        "backend_image_tag": "latest",
        "qgis_plugin_version": "latest",
        "dags_version": "0.0.0",
        "db_version": "head",
    }
    version_file.write_text(json.dumps(versions), encoding="utf-8")

    with mock.patch("pinta_backend.routes.settings.get_settings") as get_settings:
        get_settings.return_value.version_dir = tmp_path
        response = client_with_mock_airflow.get("/health")
        assert response.status_code == 200
        assert response.json()["versions"] == versions

        versions["db_version"] = "1.2.3"
        version_file.write_text(json.dumps(versions), encoding="utf-8")
        assert client_with_mock_airflow.get("/health").json()["versions"] == versions


@pytest.mark.parametrize("file_content", [None, "{bad json", "[]", "directory"])
def test_health_returns_empty_versions_when_file_is_unavailable(
    client_with_mock_airflow: testclient.TestClient,
    tmp_path: Path,
    file_content: str | None,
) -> None:
    if file_content == "directory":
        (tmp_path / "version.json").mkdir()
    elif file_content is not None:
        (tmp_path / "version.json").write_text(file_content, encoding="utf-8")

    with mock.patch("pinta_backend.routes.settings.get_settings") as get_settings:
        get_settings.return_value.version_dir = tmp_path
        response = client_with_mock_airflow.get("/health")

    assert response.status_code == 200
    assert response.json()["versions"] == {}


def test_health_returns_versions_when_airflow_is_down(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "version.json").write_text('{"db_version": "head"}', encoding="utf-8")
    mock_airflow_client.check_authentication.side_effect = exceptions.AirflowAuthError(
        "bad credentials"
    )

    with mock.patch("pinta_backend.routes.settings.get_settings") as get_settings:
        get_settings.return_value.version_dir = tmp_path
        response = client_with_mock_airflow.get("/health")

    assert response.status_code == 500
    assert response.json()["versions"] == {"db_version": "head"}


def test_health_returns_versions_when_database_is_down(
    client_with_mock_airflow: testclient.TestClient,
    mock_check_primary_db: mock.MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "version.json").write_text('{"db_version": "head"}', encoding="utf-8")
    mock_check_primary_db.side_effect = sqlalchemy.exc.OperationalError(
        "connect", {}, Exception("connection refused")
    )

    with mock.patch("pinta_backend.routes.settings.get_settings") as get_settings:
        get_settings.return_value.version_dir = tmp_path
        response = client_with_mock_airflow.get("/health")

    assert response.status_code == 500
    assert response.json()["versions"] == {"db_version": "head"}
