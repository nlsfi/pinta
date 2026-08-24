# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import types
import uuid
from typing import Any
from unittest import mock

import pytest
from fastapi import testclient
from pytest_mock import MockerFixture

from pinta_backend import db_context, exceptions, routes


@pytest.fixture
def mock_delete_job_database(mocker: MockerFixture) -> mock.MagicMock:
    """Patch the production-area service used by the route."""
    return mocker.patch.object(
        routes.production_area, "delete_job_database", autospec=True
    )


def _delete_url(production_area_id: Any) -> str:
    return f"/production-areas/{production_area_id}/database"


def test_delete_database_returns_dropped_database_name(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    area_id = str(uuid.uuid4())
    mock_delete_job_database.return_value = "job_area_1"

    response = client.delete(_delete_url(area_id))

    assert response.status_code == 200
    body = response.json()
    assert body["production_area_id"] == area_id
    assert body["database_name"] == "job_area_1"
    assert body["message"]
    mock_delete_job_database.assert_called_once_with(area_id)


def test_delete_database_returns_null_name_when_area_had_no_database(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    mock_delete_job_database.return_value = None

    response = client.delete(_delete_url(uuid.uuid4()))

    assert response.status_code == 200
    assert response.json()["database_name"] is None


def test_delete_database_rejects_a_malformed_production_area_id(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    response = client.delete(_delete_url("not-a-uuid"))

    assert response.status_code == 422
    mock_delete_job_database.assert_not_called()


def test_delete_database_returns_404_when_production_area_missing(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    area_id = str(uuid.uuid4())
    mock_delete_job_database.side_effect = exceptions.ProductionAreaNotFoundError(
        area_id
    )

    response = client.delete(_delete_url(area_id))

    assert response.status_code == 404
    assert area_id in response.json()["detail"]


def test_delete_database_returns_400_for_a_protected_database(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    mock_delete_job_database.side_effect = exceptions.JobDatabaseProtectedError(
        "job_template"
    )

    response = client.delete(_delete_url(uuid.uuid4()))

    assert response.status_code == 400
    assert "job_template" in response.json()["detail"]


def test_delete_database_returns_400_when_the_area_is_not_deletable(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    area_id = str(uuid.uuid4())
    mock_delete_job_database.side_effect = exceptions.JobDatabaseNotDeletableError(
        area_id, "started"
    )

    response = client.delete(_delete_url(area_id))

    assert response.status_code == 400
    assert "started" in response.json()["detail"]


def test_delete_database_returns_500_when_the_drop_is_refused(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    mock_delete_job_database.side_effect = exceptions.JobDatabaseDropFailedError(
        "job_area_1", "permission denied"
    )

    response = client.delete(_delete_url(uuid.uuid4()))

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "job_area_1" in detail
    # The driver's message stays in the log, not in the response.
    assert "permission denied" not in detail


def test_delete_database_returns_503_when_job_cluster_unreachable(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    mock_delete_job_database.side_effect = exceptions.JobDatabaseUnreachableError(
        "conn refused"
    )

    response = client.delete(_delete_url(uuid.uuid4()))

    assert response.status_code == 503
    assert response.json()["detail"]


def test_delete_database_returns_503_when_database_unreachable(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
) -> None:
    mock_delete_job_database.side_effect = exceptions.DatabaseUnreachableError(
        "conn refused"
    )

    response = client.delete(_delete_url(uuid.uuid4()))

    assert response.status_code == 503
    assert response.json()["detail"]


@pytest.mark.parametrize("dev_mode", [True, False])
def test_delete_database_applies_db_override_header_via_context(
    client: testclient.TestClient,
    mock_delete_job_database: mock.MagicMock,
    mocker: MockerFixture,
    dev_mode: bool,
) -> None:
    mocker.patch.object(
        db_context.settings,
        "get_settings",
        return_value=types.SimpleNamespace(development_mode=dev_mode),
    )
    captured: dict[str, str | None] = {}

    def _capture(*_args: Any, **_kwargs: Any) -> None:
        captured["db_name"] = db_context.get_db_name_override()

    mock_delete_job_database.side_effect = _capture

    response = client.delete(
        _delete_url(uuid.uuid4()),
        headers={"X-Pinta-Db-Name": "pinta_test_gw0"},
    )

    assert response.status_code == 200
    assert captured["db_name"] == ("pinta_test_gw0" if dev_mode else None)
