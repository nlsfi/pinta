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
from pytest_mock import MockerFixture

from pinta_qgis_plugin import exceptions
from pinta_qgis_plugin.api import api_client
from pinta_qgis_plugin.workflows import job_database


@pytest.fixture
def mock_api_client(mocker: MockerFixture) -> MagicMock:
    mock_client = MagicMock()
    mocker.patch.object(
        api_client,
        "get_api_client",
        autospec=True,
        return_value=mock_client,
    )
    return mock_client


@pytest.fixture
def mock_ask_confirmation(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        job_database.messages, "ask_confirmation", autospec=True, return_value=True
    )


@pytest.fixture
def mock_close_production_area(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        job_database.manager, "close_production_area", autospec=True
    )


def test_delete_job_database_delegates_to_api_client(
    mock_api_client: MagicMock,
    mock_ask_confirmation: MagicMock,
    mock_close_production_area: MagicMock,
) -> None:
    job_database.delete_job_database("area-42", "job_area_42")

    mock_ask_confirmation.assert_called_once()
    mock_api_client.delete_job_database.assert_called_once_with("area-42")
    mock_close_production_area.assert_called_once_with("job_area_42")


def test_delete_job_database_does_nothing_when_not_confirmed(
    mock_api_client: MagicMock,
    mock_ask_confirmation: MagicMock,
    mock_close_production_area: MagicMock,
) -> None:
    mock_ask_confirmation.return_value = False

    job_database.delete_job_database("area-42", "job_area_42")

    mock_api_client.delete_job_database.assert_not_called()
    mock_close_production_area.assert_not_called()


def test_delete_job_database_without_database_name_skips_layer_cleanup(
    mock_api_client: MagicMock,
    mock_ask_confirmation: MagicMock,
    mock_close_production_area: MagicMock,
) -> None:
    job_database.delete_job_database("area-42", "")

    mock_api_client.delete_job_database.assert_called_once_with("area-42")
    mock_close_production_area.assert_not_called()


def test_delete_job_database_keeps_layers_when_api_client_raises(
    mocker: MockerFixture,
    mock_api_client: MagicMock,
    mock_ask_confirmation: MagicMock,
    mock_close_production_area: MagicMock,
) -> None:
    mock_show = mocker.patch.object(
        job_database.messages, "show_error_dialog", autospec=True
    )
    mock_api_client.delete_job_database.side_effect = (
        exceptions.JobDatabaseNotDeletedError(
            "Could not delete production area database", "specific failure"
        )
    )

    job_database.delete_job_database("area-42", "job_area_42")

    mock_close_production_area.assert_not_called()
    mock_show.assert_called_once()
    title, body = mock_show.call_args.args
    assert title == "Could not delete production area database"
    assert "specific failure" in body
