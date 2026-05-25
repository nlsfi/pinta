# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import types
from typing import Any
from unittest import mock

import pytest
from airflow_client.client.exceptions import (
    ApiException,
    BadRequestException,
    ServiceException,
    UnauthorizedException,
)

from pinta_backend import airflow_client as ac_module
from pinta_backend import exceptions
from pinta_backend_test_utils import make_test_settings

pytestmark = pytest.mark.anyio


def _dag(dag_id: str, tag_names: list[str]) -> types.SimpleNamespace:
    """Build an object that quacks like a DAGResponse (id + tags)."""
    return types.SimpleNamespace(
        dag_id=dag_id,
        tags=[types.SimpleNamespace(name=name) for name in tag_names],
    )


def _dag_collection(dags: list[types.SimpleNamespace]) -> types.SimpleNamespace:
    return types.SimpleNamespace(dags=dags, total_entries=len(dags))


def _dag_details(params: dict[str, Any] | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(params=params or {})


def _patch_token_exchange(client: ac_module.AirflowClient, mocker: Any) -> mock.Mock:
    return mocker.patch.object(
        client._auth,
        "_exchange_token",
        new=mock.AsyncMock(side_effect=["token-1", "token-2"]),
    )


def _patch_dag_api(
    mocker: Any,
    *,
    dags_response: types.SimpleNamespace | None = None,
    details_response: types.SimpleNamespace | None = None,
) -> mock.Mock:
    """Mock ``DAGApi(...)`` so ``get_dags`` / ``get_dag_details`` return canned data."""
    api = mock.Mock()
    if dags_response is not None:
        api.get_dags.return_value = dags_response
    if details_response is not None:
        api.get_dag_details.return_value = details_response
    mocker.patch("pinta_backend.airflow_client.DAGApi", return_value=api)
    return api


def _patch_immediate_retry(client: ac_module.AirflowClient, mocker: Any) -> mock.Mock:
    """Make ``_call_with_retry`` invoke its callback with a fresh mock ApiClient."""

    async def _invoke(fn: Any) -> Any:
        return fn(mock.Mock())

    return mocker.patch.object(client, "_call_with_retry", side_effect=_invoke)


@pytest.fixture
def client() -> ac_module.AirflowClient:
    return ac_module.AirflowClient(make_test_settings())


async def test_call_with_retry_refreshes_on_unauthorized(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    fn = mock.Mock(side_effect=[UnauthorizedException(status=401), "ok"])

    result = await client._call_with_retry(fn)

    assert result == "ok"
    assert fn.call_count == 2


async def test_call_with_retry_raises_auth_error_on_persistent_unauthorized(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    fn = mock.Mock(side_effect=UnauthorizedException(status=401))

    with pytest.raises(exceptions.AirflowAuthError):
        await client._call_with_retry(fn)

    assert fn.call_count == 2


async def test_api_exception_with_status_zero_maps_to_unreachable(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    fn = mock.Mock(side_effect=ApiException(status=0, reason="connect refused"))

    with pytest.raises(exceptions.AirflowUnreachableError):
        await client._call_with_retry(fn)


async def test_service_exception_maps_to_airflow_api_error(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    fn = mock.Mock(side_effect=ServiceException(status=503, reason="overloaded"))

    with pytest.raises(exceptions.AirflowApiError) as excinfo:
        await client._call_with_retry(fn)

    assert excinfo.value.status == 503
    assert "overloaded" in excinfo.value.message


async def test_trigger_dag_by_tag_raises_when_no_dag_matches(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(mocker, dags_response=_dag_collection([]))
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.DagNotFoundForTagError):
        await client.trigger_dag_by_tag("missing")


async def test_trigger_dag_by_tag_raises_when_multiple_match(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("a", ["shared"]), _dag("b", ["shared"])]),
    )
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.MultipleDagsForTagError) as excinfo:
        await client.trigger_dag_by_tag("shared")
    assert sorted(excinfo.value.dag_ids) == ["a", "b"]


async def test_trigger_dag_by_tag_triggers_unique_match(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    triggered_run = types.SimpleNamespace(dag_id="solo", dag_run_id="r1")
    api = _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details(),
    )
    api.trigger_dag_run = mock.Mock(return_value=triggered_run)
    # DagRunApi(...) is constructed separately from DAGApi(...); rig it too.
    dag_run_api = mock.Mock()
    dag_run_api.trigger_dag_run.return_value = triggered_run
    mocker.patch("pinta_backend.airflow_client.DagRunApi", return_value=dag_run_api)
    _patch_immediate_retry(client, mocker)

    result = await client.trigger_dag_by_tag("unique")

    assert result is triggered_run


async def test_trigger_dag_by_tag_forwards_conf_to_airflow(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details({"folder": {"schema": {"type": "string"}}}),
    )
    dag_run_api = mock.Mock()
    mocker.patch("pinta_backend.airflow_client.DagRunApi", return_value=dag_run_api)
    _patch_immediate_retry(client, mocker)

    payload = {"folder": "/input/dem"}
    await client.trigger_dag_by_tag("unique", conf=payload)

    dag_id, body = dag_run_api.trigger_dag_run.call_args.args
    assert dag_id == "solo"
    assert body.conf == payload


async def test_trigger_dag_by_tag_rejects_unknown_param(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details({"name": {"schema": {"type": "string"}}}),
    )
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.InvalidWorkflowParametersError) as excinfo:
        await client.trigger_dag_by_tag("unique", conf={"unexpected": 1})

    assert "unexpected" in excinfo.value.message.lower()


async def test_trigger_dag_by_tag_rejects_wrong_param_type(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details({"name": {"schema": {"type": "string"}}}),
    )
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.InvalidWorkflowParametersError) as excinfo:
        await client.trigger_dag_by_tag("unique", conf={"name": 42})

    assert "name" in excinfo.value.message


async def test_param_schema_is_fetched_for_every_trigger(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    api = _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details({"name": {"schema": {"type": "string"}}}),
    )
    _patch_immediate_retry(client, mocker)
    # Don't actually issue the SDK trigger; just verify the details call count.
    mocker.patch("pinta_backend.airflow_client.DagRunApi", return_value=mock.Mock())

    await client.trigger_dag_by_tag("unique", conf={"name": "a"})
    await client.trigger_dag_by_tag("unique", conf={"name": "b"})

    assert api.get_dag_details.call_count == 2


async def test_trigger_dag_by_tag_propagates_api_error_from_schema_fetch(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    api = _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
    )
    api.get_dag_details.side_effect = exceptions.AirflowApiError(
        500, "Internal Server Error"
    )
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.AirflowApiError) as excinfo:
        await client.trigger_dag_by_tag("unique", conf={})

    assert excinfo.value.status == 500


async def test_trigger_dag_by_tag_propagates_unreachable_from_schema_fetch(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    api = _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
    )
    msg = "dns"
    api.get_dag_details.side_effect = exceptions.AirflowUnreachableError(msg)
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.AirflowUnreachableError):
        await client.trigger_dag_by_tag("unique", conf={})


async def test_trigger_dag_by_tag_raises_invalid_parameters_on_bad_request(
    client: ac_module.AirflowClient, mocker: Any
) -> None:
    _patch_token_exchange(client, mocker)
    _patch_dag_api(
        mocker,
        dags_response=_dag_collection([_dag("solo", ["unique"])]),
        details_response=_dag_details(),
    )
    dag_run_api = mock.Mock()
    bad_request = BadRequestException(status=400, reason="Bad Request")
    bad_request.body = '{"detail": "\'folder\' is a required property"}'
    dag_run_api.trigger_dag_run.side_effect = bad_request
    mocker.patch("pinta_backend.airflow_client.DagRunApi", return_value=dag_run_api)
    _patch_immediate_retry(client, mocker)

    with pytest.raises(exceptions.InvalidWorkflowParametersError) as excinfo:
        await client.trigger_dag_by_tag("unique", conf={})

    assert "'folder'" in excinfo.value.message
