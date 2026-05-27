# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import types
import uuid
from typing import Any
from unittest import mock

import pytest
from fastapi import testclient
from pytest_mock import MockerFixture

from pinta_backend import exceptions, routes


def _dag_run(dag_id: str = "print_hello_world", run_id: str = "manual__1") -> Any:
    return types.SimpleNamespace(dag_id=dag_id, dag_run_id=run_id)


@pytest.fixture
def mock_mark_as_queued(mocker: MockerFixture) -> mock.MagicMock:
    """Patch the production-area service used by the route."""
    return mocker.patch.object(routes.production_area, "mark_as_queued", autospec=True)


def _yields(value: Any | None = None) -> Any:
    @contextlib.contextmanager
    def _cm(*_args: Any, **_kwargs: Any) -> Any:
        yield value

    return _cm


def test_trigger_workflow_returns_dag_run_on_success(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
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
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
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
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
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
    mock_mark_as_queued: mock.MagicMock,
    exc: Exception,
    expected_status: int,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
    mock_airflow_client.trigger_dag_by_tag.side_effect = exc

    response = client_with_mock_airflow.post("/workflows/some-tag")

    assert response.status_code == expected_status
    assert response.json()["detail"]


def test_trigger_workflow_passes_production_area_id_to_service(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
    mock_airflow_client.trigger_dag_by_tag.return_value = _dag_run()
    area_id = str(uuid.uuid4())

    response = client_with_mock_airflow.post(
        "/workflows/hello", json={"production_area_id": area_id}
    )

    assert response.status_code == 202
    mock_mark_as_queued.assert_called_once_with(area_id)


def test_trigger_workflow_passes_none_to_service_when_id_absent(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = _yields()
    mock_airflow_client.trigger_dag_by_tag.return_value = _dag_run()

    response = client_with_mock_airflow.post("/workflows/hello", json={})

    assert response.status_code == 202
    mock_mark_as_queued.assert_called_once_with(None)


def test_trigger_workflow_returns_503_when_database_unreachable(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    mock_mark_as_queued.side_effect = exceptions.DatabaseUnreachableError(
        "conn refused"
    )

    response = client_with_mock_airflow.post(
        "/workflows/hello", json={"production_area_id": str(uuid.uuid4())}
    )

    assert response.status_code == 503
    assert response.json()["detail"]
    mock_airflow_client.trigger_dag_by_tag.assert_not_called()


def test_trigger_workflow_returns_404_when_production_area_missing(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    area_id = str(uuid.uuid4())
    mock_mark_as_queued.side_effect = exceptions.ProductionAreaNotFoundError(area_id)

    response = client_with_mock_airflow.post(
        "/workflows/hello", json={"production_area_id": area_id}
    )

    assert response.status_code == 404
    assert area_id in response.json()["detail"]
    mock_airflow_client.trigger_dag_by_tag.assert_not_called()


def test_trigger_workflow_propagates_trigger_error_through_service_block(
    client_with_mock_airflow: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
    mock_mark_as_queued: mock.MagicMock,
) -> None:
    """A failing Airflow trigger must propagate out through ``mark_as_queued`` so
    the service's restore-on-exception branch runs."""
    saw_exception = False

    @contextlib.contextmanager
    def _capturing_cm(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal saw_exception
        try:
            yield None
        except BaseException:
            saw_exception = True
            raise

    mock_mark_as_queued.side_effect = _capturing_cm
    mock_airflow_client.trigger_dag_by_tag.side_effect = (
        exceptions.AirflowUnreachableError("dns")
    )

    response = client_with_mock_airflow.post(
        "/workflows/hello", json={"production_area_id": str(uuid.uuid4())}
    )

    assert response.status_code == 502
    assert saw_exception
