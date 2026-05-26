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

from pytest_mock import MockerFixture

from pinta_qgis_plugin.utils import layer_utils


def _make_layer(
    mocker: MockerFixture,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    action_manager = mocker.MagicMock()
    attribute_table_config = mocker.MagicMock()
    attribute_table_config.ActionWidgetStyle.ButtonList = "button-list"
    layer = mocker.MagicMock()
    layer.actions.return_value = action_manager
    layer.attributeTableConfig.return_value = attribute_table_config
    return layer, action_manager, attribute_table_config


def test_add_action_to_vector_layer_creates_python_action(
    mocker: MockerFixture,
) -> None:
    layer, action_manager, _ = _make_layer(mocker)
    action = mocker.MagicMock()
    mock_qgs_action = mocker.patch.object(layer_utils, "QgsAction", autospec=True)
    mock_qgs_action.GenericPython = "generic-python"
    mock_qgs_action.return_value = action

    layer_utils.add_action_to_vector_layer(
        layer,
        description="desc",
        short_title="title",
        command="print('hi')",
    )

    mock_qgs_action.assert_called_once_with(
        "generic-python",
        description="desc",
        action="print('hi')",
        icon=None,
        capture=True,
        shortTitle="title",
        actionScopes=["Feature"],
    )
    action.setCommand.assert_called_once_with("print('hi')")
    action_manager.addAction.assert_called_once_with(action)


def test_add_action_to_vector_layer_respects_custom_scopes(
    mocker: MockerFixture,
) -> None:
    layer, _, _ = _make_layer(mocker)
    mock_qgs_action = mocker.patch.object(layer_utils, "QgsAction", autospec=True)

    layer_utils.add_action_to_vector_layer(
        layer,
        description="desc",
        short_title="title",
        command="print('hi')",
        scopes=("Feature", "Layer"),
    )

    assert mock_qgs_action.call_args.kwargs["actionScopes"] == ["Feature", "Layer"]


def test_add_action_to_vector_layer_enables_action_widget_in_attribute_table(
    mocker: MockerFixture,
) -> None:
    layer, _, attribute_table_config = _make_layer(mocker)
    mocker.patch.object(layer_utils, "QgsAction", autospec=True)

    layer_utils.add_action_to_vector_layer(
        layer,
        description="desc",
        short_title="title",
        command="print('hi')",
    )

    attribute_table_config.setActionWidgetVisible.assert_called_once_with(True)
    attribute_table_config.setActionWidgetStyle.assert_called_once_with("button-list")
    layer.setAttributeTableConfig.assert_called_once_with(attribute_table_config)
