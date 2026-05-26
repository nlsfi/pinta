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
from qgis_plugin_tools.tools.exceptions import QgsPluginException

from pinta_qgis_plugin.utils import messages


def test_popup_if_fails_returns_value_on_success() -> None:
    @messages.popup_if_fails
    def fn(value: int) -> int:
        return value + 1

    assert fn(1) == 2


@pytest.mark.parametrize(
    ("error", "expected_title", "expected_body"),
    [
        (
            QgsPluginException("boom", bar_msg={"details": "more details"}),
            "boom",
            "boom\n\nmore details",
        ),
        (
            QgsPluginException("boom"),
            "boom",
            "boom\n\n",
        ),
        (
            QgsPluginException("", bar_msg={"details": "details"}),
            "Error occurred",
            "Error occurred\n\ndetails",
        ),
        (
            RuntimeError("unexpected"),
            "Unhandled exception occurred",
            "An unhandled exception occurred. Check the log for more details.",
        ),
    ],
    ids=[
        "qgs_plugin_exception_with_details",
        "qgs_plugin_exception_empty_bar_msg",
        "qgs_plugin_exception_empty_message",
        "unhandled_exception",
    ],
)
def test_popup_if_fails_shows_dialog_with_expected_title_and_body(
    mocker: MockerFixture,
    error: Exception,
    expected_title: str,
    expected_body: str,
) -> None:
    mock_show = mocker.patch.object(messages, "show_error_dialog", autospec=True)

    @messages.popup_if_fails
    def fn() -> None:
        raise error

    fn()

    mock_show.assert_called_once()
    title, body = mock_show.call_args.args
    assert title == expected_title
    assert body == expected_body


def test_popup_if_fails_swallows_exception(mocker: MockerFixture) -> None:
    mocker.patch.object(messages, "show_error_dialog", autospec=True)
    error = QgsPluginException("boom")

    @messages.popup_if_fails
    def fn() -> None:
        raise error

    fn()


def test_show_error_dialog_creates_message_box(mocker: MockerFixture) -> None:
    mock_iface = mocker.patch.object(messages, "iface", autospec=True)
    mock_iface.mainWindow.return_value = MagicMock()
    mock_message_box_class = mocker.patch.object(messages, "QMessageBox")
    mock_box = MagicMock()
    mock_message_box_class.return_value = mock_box

    messages.show_error_dialog("the title", "the body")

    mock_box.setWindowTitle.assert_called_once_with("the title")
    mock_box.setText.assert_called_once_with("the body")
    mock_box.exec.assert_called_once_with()
