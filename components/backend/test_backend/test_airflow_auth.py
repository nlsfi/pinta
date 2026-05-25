# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any
from unittest import mock

import httpx
import pytest

from pinta_backend import airflow_auth, exceptions
from pinta_backend_test_utils import make_test_settings

pytestmark = pytest.mark.anyio


def _patch_token_exchange(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> mock.Mock:
    return mocker.patch.object(
        authenticator,
        "_exchange_token",
        new=mock.AsyncMock(side_effect=["token-1", "token-2"]),
    )


def _patch_httpx_post(mocker: Any, response: httpx.Response | Exception) -> mock.Mock:
    if isinstance(response, Exception):
        return mocker.patch(
            "httpx.AsyncClient.post", new=mock.AsyncMock(side_effect=response)
        )
    return mocker.patch(
        "httpx.AsyncClient.post", new=mock.AsyncMock(return_value=response)
    )


@pytest.fixture
def authenticator() -> airflow_auth.AirflowAuthenticator:
    return airflow_auth.AirflowAuthenticator(make_test_settings())


async def test_token_is_cached_across_calls(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    token_mock = _patch_token_exchange(authenticator, mocker)

    assert await authenticator.get_token() == "token-1"
    assert await authenticator.get_token() == "token-1"
    assert token_mock.await_count == 1


async def test_refresh_token_forces_new_exchange(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    token_mock = _patch_token_exchange(authenticator, mocker)

    assert await authenticator.get_token() == "token-1"
    assert await authenticator.refresh_token() == "token-2"
    assert await authenticator.get_token() == "token-2"
    assert token_mock.await_count == 2


async def test_exchange_token_uses_access_token_field(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    _patch_httpx_post(mocker, httpx.Response(200, json={"access_token": "abc"}))

    assert await authenticator._exchange_token() == "abc"


async def test_exchange_token_raises_auth_error_on_bad_credentials(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    _patch_httpx_post(mocker, httpx.Response(401, json={"detail": "nope"}))

    with pytest.raises(exceptions.AirflowAuthError):
        await authenticator._exchange_token()


async def test_exchange_token_raises_auth_error_on_non_json_response(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    _patch_httpx_post(mocker, httpx.Response(200, text="not json"))

    with pytest.raises(exceptions.AirflowAuthError):
        await authenticator._exchange_token()


async def test_exchange_token_raises_auth_error_when_access_token_missing(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    _patch_httpx_post(mocker, httpx.Response(200, json={"unrelated": "field"}))

    with pytest.raises(exceptions.AirflowAuthError):
        await authenticator._exchange_token()


async def test_exchange_token_raises_unreachable_on_network_error(
    authenticator: airflow_auth.AirflowAuthenticator, mocker: Any
) -> None:
    _patch_httpx_post(mocker, httpx.ConnectError("nope"))

    with pytest.raises(exceptions.AirflowUnreachableError):
        await authenticator._exchange_token()
