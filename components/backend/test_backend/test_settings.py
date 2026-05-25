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
