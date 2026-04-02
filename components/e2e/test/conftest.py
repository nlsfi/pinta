# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from collections.abc import Iterator

import pytest
import qgis.utils
from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils
from pinta_e2e_utils import constants
from pinta_test_utils import xdist_utils
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

if typing.TYPE_CHECKING:
    from pathlib import Path

    from pinta_qgis_plugin.plugin import Plugin
    from qgis.gui import QgisInterface
    from sqlmodel import Session

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


@pytest.fixture
def created_db(worker_id: str) -> str:
    return db_utils.create_db(worker_id)


@pytest.fixture
def db(created_db: str) -> Iterator["Session"]:
    with engine_utils.get_session(
        db_utils.get_writer_credentials(created_db)
    ) as session:
        yield session
        session.close()


@pytest.fixture
def _set_env_variables(
    created_db: str, worker_id: str, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    monkeypatch.setenv("DB_NAME", created_db)
    monkeypatch.setenv("DB_SRID", constants.SRID)


@pytest.fixture
def qgis_plugin(
    _set_env_variables: None,
    qgis_new_project: None,
    qgis_iface: "QgisInterface",
    tmp_path: "Path",
) -> typing.Generator["Plugin", None, None]:
    """
    Initialize and return the plugin object.
    """
    from pinta_qgis_plugin import classFactory

    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(constants.SRID))
    plugin = classFactory(qgis_iface)
    qgis.utils.plugins["pinta"] = plugin

    plugin.initGui()
    yield plugin
    plugin.unload()
