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
import typing
from pathlib import Path

import pytest
from pinta_test_utils import xdist_utils
from qgis.core import QgsProject, QgsVectorLayer

if typing.TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

"""
!!! IMPORTANT !!!
DO NOT import anything that imports qgis.utils.iface
(or some module that imports other module that imports it) in conftest root!
Importing those modules in fixtures is OK.

The same goes with pinta_qgis_plugin.env.py.
"""


@pytest.hookimpl
def pytest_xdist_auto_num_workers(config: "pytest.Config"):
    return xdist_utils.get_number_of_workers(config)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: "pytest.Config") -> None:
    """Set environment variables for tests."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PINTA_INITIAL_PROJECT_EXTENT", "0,0,10,10")
    monkeypatch.setenv("DB_SRID", 3067)


@pytest.fixture(autouse=True)
def reset_session_state(
    qgis_new_project: None,
):
    QgsProject.instance().clear()


@pytest.fixture
def empty_multipolygon_layer() -> QgsVectorLayer:
    return QgsVectorLayer("MultiPolygon", "Empty", "memory")


@pytest.fixture
def data_path(request: "SubRequest") -> Path:
    return Path(__file__).parent / "data"
