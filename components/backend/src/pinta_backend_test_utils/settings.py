# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pydantic

from pinta_backend import settings


def make_test_settings(
    *,
    airflow_base_url: str = "http://airflow.test/",
    airflow_username: str = "test-user",
    airflow_password: str = "test-password",  # noqa: S107
    airflow_http_timeout: float = 5.0,
) -> settings.Settings:
    """Build a ``Settings`` instance without reading the environment."""
    return settings.Settings.model_construct(
        airflow_base_url=pydantic.AnyHttpUrl(airflow_base_url),
        airflow_username=airflow_username,
        airflow_password=pydantic.SecretStr(airflow_password),
        airflow_http_timeout=airflow_http_timeout,
    )
