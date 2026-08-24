# Copyright (C) 2026 Pinta QGIS Plugin Contributors.
#
#
# This file is part of Pinta QGIS Plugin.
#
# Pinta QGIS Plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Pinta QGIS Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Pinta QGIS Plugin.  If not, see <https://www.gnu.org/licenses/>.

from unittest.mock import MagicMock

import pytest
import requests
from pinta_common import constants
from pytest_mock import MockerFixture

from pinta_qgis_plugin import exceptions
from pinta_qgis_plugin.api import api_client

EXPECTED_URL = f"http://example.test/workflows/{constants.DAG_ID_CALCULATE_RASTERS_FOR_PRODUCTION_AREA}"


@pytest.fixture
def client() -> api_client.PintaAPIClient:
    return api_client.PintaAPIClient("http://example.test/")


@pytest.fixture
def mock_post(mocker: MockerFixture, client: api_client.PintaAPIClient) -> MagicMock:
    mock = mocker.patch.object(client.session, "post", autospec=True)
    mock.return_value.json.return_value = {
        "message": "Reference DEM workflow task created successfully",
        "dag_id": constants.DAG_ID_CALCULATE_REFERENCE_DEM,
        "dag_run_id": "manual__2026-01-01T00:00:00+00:00",
    }
    return mock


def test_init_sets_accept_language_header() -> None:
    client = api_client.PintaAPIClient("http://example.test")
    assert "Accept-Language" in client.session.headers


@pytest.mark.parametrize("dev_mode", [True, False])
def test_init_sets_db_name_header_in_development_mode(
    mocker: MockerFixture, dev_mode: bool
) -> None:
    mocker.patch.object(api_client.env, "IS_DEVELOPMENT_MODE", dev_mode)
    mocker.patch.object(api_client.env, "PINTA_DB_NAME", "pinta_test_gw0")

    client = api_client.PintaAPIClient("http://example.test")

    if dev_mode:
        assert client.session.headers["X-Pinta-Db-Name"] == "pinta_test_gw0"
    else:
        assert "X-Pinta-Db-Name" not in client.session.headers


def test_start_reference_dem_workflow_posts_workflow_payload(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_reference_dem_workflow("area-1")

    mock_post.assert_called_once_with(
        EXPECTED_URL,
        json={
            "parameters": {
                "id": "area-1",
                "calculate_reference_dem": True,
                "calculate_dem_diff": True,
                "cluster_diff_polygons": True,
                "initialize_dem_preview": True,
            },
            "production_area_id": "area-1",
        },
        timeout=10,
    )
    mock_post.return_value.raise_for_status.assert_called_once_with()


def test_start_reference_dem_workflow_shows_success_message(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_msg_bar = mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_reference_dem_workflow("area-1")

    mock_msg_bar.info.assert_called_once()
    assert mock_msg_bar.info.call_args.kwargs == {"success": True}


def test_start_reference_dem_workflow_emits_workflow_started(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)
    received: list[tuple[str, str]] = []
    client.workflow_started.connect(
        lambda dag_id, dag_run_id: received.append((dag_id, dag_run_id))
    )

    client.start_reference_dem_workflow("area-1")

    assert received == [
        (
            constants.DAG_ID_CALCULATE_REFERENCE_DEM,
            "manual__2026-01-01T00:00:00+00:00",
        )
    ]


def test_start_reference_dem_workflow_connection_error_raises_api_connection_error(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
) -> None:
    mock_post.side_effect = requests.exceptions.ConnectionError("boom")

    with pytest.raises(exceptions.ApiConnectionError):
        client.start_reference_dem_workflow("area-1")


def test_start_reference_dem_workflow_http_error_with_detail_raises_workflow_error(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
) -> None:
    response = MagicMock(spec=requests.Response)
    response.json.return_value = {"detail": "specific failure"}
    http_error = requests.exceptions.HTTPError(response=response)
    mock_post.return_value.raise_for_status.side_effect = http_error

    with pytest.raises(exceptions.WorkflowNotStartedError) as exc_info:
        client.start_reference_dem_workflow("area-1")

    assert exc_info.value.bar_msg["details"] == "specific failure"


def test_start_reference_dem_workflow_http_error_without_json_detail_uses_fallback_detail(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
) -> None:
    response = MagicMock(spec=requests.Response)
    response.json.side_effect = requests.exceptions.JSONDecodeError("err", "", 0)
    response.text = "500 internal"
    response.url = "http://example.test/workflows/"
    http_error = requests.exceptions.HTTPError(response=response)
    mock_post.return_value.raise_for_status.side_effect = http_error

    with pytest.raises(exceptions.WorkflowNotStartedError) as exc_info:
        client.start_reference_dem_workflow("area-1")

    assert exc_info.value.bar_msg["details"] == "Check log for more details"


def test_start_reference_dem_workflow_http_error_with_none_detail_uses_fallback(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
) -> None:
    response = MagicMock(spec=requests.Response)
    response.json.return_value = {"detail": None}
    response.text = "boom"
    response.url = EXPECTED_URL
    http_error = requests.exceptions.HTTPError(response=response)
    mock_post.return_value.raise_for_status.side_effect = http_error

    with pytest.raises(exceptions.WorkflowNotStartedError) as exc_info:
        client.start_reference_dem_workflow("area-1")

    assert exc_info.value.bar_msg["details"] == "Check log for more details"


def test_start_reference_dem_workflow_http_error_without_response_uses_fallback_detail(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
) -> None:
    http_error = requests.exceptions.HTTPError(response=None)
    mock_post.return_value.raise_for_status.side_effect = http_error

    with pytest.raises(exceptions.WorkflowNotStartedError) as exc_info:
        client.start_reference_dem_workflow("area-1")

    assert exc_info.value.bar_msg["details"] == "Check log for more details"


def test_start_dissolve_update_areas_workflow_posts_workflow_payload(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_dissolve_update_areas_workflow("area-1")

    expected_url = (
        f"http://example.test/workflows/{constants.DAG_ID_DISSOLVE_UPDATE_AREAS}"
    )
    mock_post.assert_called_once_with(
        expected_url,
        json={
            "parameters": {"id": "area-1"},
            "production_area_id": "area-1",
        },
        timeout=10,
    )
    mock_post.return_value.raise_for_status.assert_called_once_with()


def test_start_dissolve_update_areas_workflow_shows_success_message(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_msg_bar = mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_dissolve_update_areas_workflow("area-1")

    mock_msg_bar.info.assert_called_once()
    assert mock_msg_bar.info.call_args.kwargs == {"success": True}


def test_start_register_update_areas_workflow_posts_workflow_payload(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_register_update_areas_workflow("area-1")

    expected_url = (
        f"http://example.test/workflows/{constants.DAG_ID_REGISTER_UPDATE_AREAS}"
    )
    mock_post.assert_called_once_with(
        expected_url,
        json={
            "parameters": {"id": "area-1"},
            "production_area_id": "area-1",
        },
        timeout=10,
    )
    mock_post.return_value.raise_for_status.assert_called_once_with()


def test_start_register_update_areas_workflow_shows_success_message(
    client: api_client.PintaAPIClient,
    mock_post: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_msg_bar = mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.start_register_update_areas_workflow("area-1")

    mock_msg_bar.info.assert_called_once()
    assert mock_msg_bar.info.call_args.kwargs == {"success": True}


@pytest.fixture
def mock_delete(mocker: MockerFixture, client: api_client.PintaAPIClient) -> MagicMock:
    return mocker.patch.object(client.session, "delete", autospec=True)


def test_delete_job_database_calls_delete_endpoint(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.delete_job_database("area-1")

    mock_delete.assert_called_once_with(
        "http://example.test/production-areas/area-1/database",
        timeout=10,
    )
    mock_delete.return_value.raise_for_status.assert_called_once_with()


def test_delete_job_database_shows_success_message(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_msg_bar = mocker.patch.object(api_client, "MsgBar", autospec=True)

    client.delete_job_database("area-1")

    mock_msg_bar.info.assert_called_once()
    assert mock_msg_bar.info.call_args.kwargs == {"success": True}


def test_delete_job_database_emits_job_database_deleted(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(api_client, "MsgBar", autospec=True)
    received: list[str] = []
    client.job_database_deleted.connect(received.append)

    client.delete_job_database("area-1")

    assert received == ["area-1"]


def test_delete_job_database_connection_error_raises_api_connection_error(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
) -> None:
    mock_delete.side_effect = requests.exceptions.ConnectionError("boom")

    with pytest.raises(exceptions.ApiConnectionError):
        client.delete_job_database("area-1")


def test_delete_job_database_http_error_raises_job_database_error(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
) -> None:
    response = MagicMock(spec=requests.Response)
    response.json.return_value = {"detail": "database is protected"}
    mock_delete.return_value.raise_for_status.side_effect = (
        requests.exceptions.HTTPError(response=response)
    )

    with pytest.raises(exceptions.JobDatabaseNotDeletedError) as exc_info:
        client.delete_job_database("area-1")

    assert exc_info.value.bar_msg["details"] == "database is protected"


def test_delete_job_database_does_not_emit_signal_on_error(
    client: api_client.PintaAPIClient,
    mock_delete: MagicMock,
) -> None:
    received: list[str] = []
    client.job_database_deleted.connect(received.append)
    response = MagicMock(spec=requests.Response)
    response.json.return_value = {"detail": "boom"}
    mock_delete.return_value.raise_for_status.side_effect = (
        requests.exceptions.HTTPError(response=response)
    )

    with pytest.raises(exceptions.JobDatabaseNotDeletedError):
        client.delete_job_database("area-1")

    assert received == []


def test_get_api_client_is_cached() -> None:
    api_client.get_api_client.cache_clear()
    try:
        first = api_client.get_api_client()
        second = api_client.get_api_client()
    finally:
        api_client.get_api_client.cache_clear()

    assert first is second
