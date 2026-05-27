# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import functools

import pydantic
import pydantic_settings


def _aliases(*names: str) -> pydantic.AliasChoices:
    """Build a tuple of acceptable env-var names for a settings field."""
    return pydantic.AliasChoices(*names)


class Settings(pydantic_settings.BaseSettings):
    """Pinta backend runtime configuration loaded from the environment.

    Each Airflow-related field accepts two env-var names: the namespaced
    ``PINTA_BACKEND_AIRFLOW_*`` form (preferred in shared ``.env`` files) and
    the bare ``AIRFLOW_*`` form (matches the production Ansible contract).
    """

    # Airflow settings
    airflow_base_url: pydantic.AnyHttpUrl = pydantic.Field(
        validation_alias=_aliases("PINTA_BACKEND_AIRFLOW_BASE_URL", "AIRFLOW_BASE_URL"),
    )
    airflow_username: str = pydantic.Field(
        validation_alias=_aliases("PINTA_BACKEND_AIRFLOW_USERNAME", "AIRFLOW_USERNAME"),
    )
    airflow_password: pydantic.SecretStr = pydantic.Field(
        validation_alias=_aliases("PINTA_BACKEND_AIRFLOW_PASSWORD", "AIRFLOW_PASSWORD"),
    )
    airflow_http_timeout: float = pydantic.Field(
        default=10.0,
        validation_alias=_aliases(
            "PINTA_BACKEND_AIRFLOW_HTTP_TIMEOUT", "AIRFLOW_HTTP_TIMEOUT"
        ),
    )
    api_host: str = pydantic.Field(
        default="0.0.0.0",  # noqa: S104
        validation_alias="PINTA_BACKEND_HOST",
    )
    api_port: int = pydantic.Field(
        default=3011,
        validation_alias="PINTA_BACKEND_PORT",
    )

    # Database settings
    primary_db_host: str = pydantic.Field(validation_alias="DB_PRIMARY_HOST")
    primary_db_port: str = pydantic.Field(validation_alias="DB_PRIMARY_PORT")
    primary_db_name: str = pydantic.Field(validation_alias="DB_PRIMARY_NAME")
    # TODO: add new user for backend
    primary_db_user: str = pydantic.Field(
        validation_alias="DB_PRIMARY_PROCESSING_WORKER_USER"
    )
    primary_db_password: pydantic.SecretStr = pydantic.Field(
        validation_alias="DB_PRIMARY_PROCESSING_WORKER_PASSWORD"
    )

    model_config = pydantic_settings.SettingsConfigDict(extra="ignore")

    @property
    def primary_db_uri(self) -> str:
        """Primary database connection URI."""
        return (
            f"postgresql+psycopg://{self.primary_db_user}:{self.primary_db_password.get_secret_value()}"
            f"@{self.primary_db_host}:{self.primary_db_port}/{self.primary_db_name}"
        )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached `Settings` built from the current environment."""
    return Settings()
