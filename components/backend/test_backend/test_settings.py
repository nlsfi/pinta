# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest

from pinta_backend import settings


@pytest.mark.parametrize(
    ("base_url_var", "username_var", "password_var", "timeout_var"),
    [
        (
            "PINTA_BACKEND_AIRFLOW_BASE_URL",
            "PINTA_BACKEND_AIRFLOW_USERNAME",
            "PINTA_BACKEND_AIRFLOW_PASSWORD",
            "PINTA_BACKEND_AIRFLOW_HTTP_TIMEOUT",
        ),
        (
            "AIRFLOW_BASE_URL",
            "AIRFLOW_USERNAME",
            "AIRFLOW_PASSWORD",
            "AIRFLOW_HTTP_TIMEOUT",
        ),
    ],
)
def test_settings_reads_both_namespaced_and_bare_env_vars(
    monkeypatch: pytest.MonkeyPatch,
    base_url_var: str,
    username_var: str,
    password_var: str,
    timeout_var: str,
) -> None:
    for var in (
        "PINTA_BACKEND_AIRFLOW_BASE_URL",
        "PINTA_BACKEND_AIRFLOW_USERNAME",
        "PINTA_BACKEND_AIRFLOW_PASSWORD",
        "PINTA_BACKEND_AIRFLOW_HTTP_TIMEOUT",
        "AIRFLOW_BASE_URL",
        "AIRFLOW_USERNAME",
        "AIRFLOW_PASSWORD",
        "AIRFLOW_HTTP_TIMEOUT",
    ):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv(base_url_var, "http://airflow.example/")
    monkeypatch.setenv(username_var, "service-user")
    monkeypatch.setenv(password_var, "service-secret")
    monkeypatch.setenv(timeout_var, "7.5")

    loaded = settings.Settings()

    assert str(loaded.airflow_base_url) == "http://airflow.example/"
    assert loaded.airflow_username == "service-user"
    assert loaded.airflow_password.get_secret_value() == "service-secret"
    assert loaded.airflow_http_timeout == 7.5
    assert loaded.api_host == "0.0.0.0"
    assert loaded.api_port == 3011


def test_settings_reads_uvicorn_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_BASE_URL", "http://airflow.example/")
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_USERNAME", "service-user")
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_PASSWORD", "service-secret")
    monkeypatch.setenv("PINTA_BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("PINTA_BACKEND_PORT", "8020")

    loaded = settings.Settings()

    assert loaded.api_host == "127.0.0.1"
    assert loaded.api_port == 8020


def _set_required_airflow_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_BASE_URL", "http://airflow.example/")
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_USERNAME", "service-user")
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_PASSWORD", "service-secret")


def test_primary_db_uri_for_targets_given_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_airflow_env(monkeypatch)
    loaded = settings.Settings()

    assert loaded.primary_db_uri_for("pinta_test_gw0").endswith("/pinta_test_gw0")
    assert loaded.primary_db_uri.endswith(f"/{loaded.primary_db_name}")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("1", True), ("false", False), ("0", False)],
)
def test_settings_reads_development_mode(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    _set_required_airflow_env(monkeypatch)
    monkeypatch.setenv("PINTA_DEVELOPMENT_MODE", value)

    assert settings.Settings().development_mode is expected
