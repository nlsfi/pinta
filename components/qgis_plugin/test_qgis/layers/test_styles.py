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

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from pinta_qgis_plugin.layers import styles


@pytest.fixture
def mock_layer() -> MagicMock:
    layer = MagicMock()
    layer.name.return_value = "Test layer"
    return layer


def test_apply_style_calls_load_named_style(mock_layer: MagicMock):
    mock_layer.loadNamedStyle.return_value = ("", True)
    styles.apply_style(mock_layer, Path("/some/style.qml"))
    mock_layer.loadNamedStyle.assert_called_once_with("/some/style.qml")


def test_apply_style_calls_trigger_repaint(mock_layer: MagicMock):
    mock_layer.loadNamedStyle.return_value = ("", True)
    styles.apply_style(mock_layer, Path("/some/style.qml"))
    mock_layer.triggerRepaint.assert_called_once()


def test_apply_style_logs_warning_on_failure(
    mock_layer: MagicMock, mocker: MockerFixture
):
    mock_layer.loadNamedStyle.return_value = ("Style not found", False)
    mock_logger = mocker.patch.object(styles, "LOGGER")
    styles.apply_style(mock_layer, Path("/missing/style.qml"))
    mock_logger.warning.assert_called_once()
    mock_layer.triggerRepaint.assert_called_once()
