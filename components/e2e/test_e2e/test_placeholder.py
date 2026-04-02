# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
from typing import TYPE_CHECKING

from qgis._core import QgsProject

if TYPE_CHECKING:
    from pinta_qgis_plugin import Plugin


def test_placeholder(qgis_plugin: "Plugin"):
    assert len(QgsProject.instance().mapLayers()) == 2
