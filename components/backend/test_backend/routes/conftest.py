# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterator
from unittest import mock

import pytest
from fastapi import testclient

from pinta_backend import airflow_client, app


@pytest.fixture
def mock_airflow_client() -> mock.AsyncMock:
    return mock.AsyncMock(spec=airflow_client.AirflowClient)


@pytest.fixture(autouse=True)
def mock_check_primary_db() -> Iterator[mock.MagicMock]:
    with mock.patch("pinta_backend.routes.db.check_primary_db") as m:
        yield m


@pytest.fixture
def client_with_mock_airflow(
    client: testclient.TestClient,
    mock_airflow_client: mock.AsyncMock,
) -> Iterator[testclient.TestClient]:
    app.api.dependency_overrides[airflow_client.get_airflow_client] = lambda: (
        mock_airflow_client
    )
    try:
        yield client
    finally:
        app.api.dependency_overrides.clear()
