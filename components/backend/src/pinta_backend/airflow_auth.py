# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import asyncio
import logging

import httpx

from pinta_backend import exceptions, settings

LOGGER = logging.getLogger(__name__)


class AirflowAuthenticator:
    """Caches and refreshes the JWT used to talk to Airflow."""

    def __init__(self, app_settings: settings.Settings) -> None:
        self._settings = app_settings
        self._token: str | None = None
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Return the Airflow REST API base URL without a trailing slash."""
        return str(self._settings.airflow_base_url).rstrip("/")

    async def get_token(self) -> str:
        """Return the cached token, exchanging credentials on first use."""
        if self._token is not None:
            return self._token
        async with self._lock:
            if self._token is None:
                self._token = await self._exchange_token()
            return self._token

    async def refresh_token(self) -> str:
        """Force a fresh token exchange and return the new token."""
        async with self._lock:
            self._token = None
            self._token = await self._exchange_token()
            return self._token

    async def _exchange_token(self) -> str:
        url = f"{self.base_url}/auth/token"
        payload = {
            "username": self._settings.airflow_username,
            "password": self._settings.airflow_password.get_secret_value(),
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.airflow_http_timeout,
            ) as client:
                response = await client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
        except httpx.RequestError as exc:
            raise exceptions.AirflowUnreachableError(str(exc)) from exc

        if not response.is_success:
            LOGGER.warning(
                "Token exchange failed: %d %s",
                response.status_code,
                response.text[:500],
            )
            msg = f"Token exchange failed with status {response.status_code}"
            raise exceptions.AirflowAuthError(msg)
        try:
            data = response.json()
        except ValueError as exc:
            msg = "Non-JSON token response"
            raise exceptions.AirflowAuthError(msg) from exc

        token = data.get("access_token")
        if not token:
            msg = "Token response missing access_token"
            raise exceptions.AirflowAuthError(msg)
        return token
