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

from pinta_qgis_plugin.layers import manager, vector_layer


@pytest.fixture
def mock_add_vector_layers(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        vector_layer,
        "add_vector_layers",
        autospec=True,
    )


def test_create_layer_with_valid_layer_returns_layer(
    mock_add_vector_layers: MagicMock,
):
    manager.initialize_layers()
    mock_add_vector_layers.assert_called_once()
