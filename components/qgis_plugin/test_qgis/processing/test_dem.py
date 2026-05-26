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
from pinta_qgis_plugin.workflows import dem


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


def test_start_reference_dem_workflow_delegates_to_api_client(
    mock_api_client: MagicMock,
) -> None:
    dem.start_reference_dem_workflow("area-42")

    mock_api_client.start_reference_dem_workflow.assert_called_once_with("area-42")


def test_start_reference_dem_workflow_shows_popup_when_api_client_raises(
    mocker: MockerFixture, mock_api_client: MagicMock
) -> None:
    mock_show = mocker.patch.object(dem.messages, "show_error_dialog", autospec=True)
    mock_api_client.start_reference_dem_workflow.side_effect = (
        exceptions.WorkflowNotStartedError(
            "Could not start workflow", "specific failure"
        )
    )

    dem.start_reference_dem_workflow("area-42")

    mock_show.assert_called_once()
    title, body = mock_show.call_args.args
    assert title == "Could not start workflow"
    assert "specific failure" in body
