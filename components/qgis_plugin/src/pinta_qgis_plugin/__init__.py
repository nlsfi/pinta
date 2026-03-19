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

from qgis.PyQt import QtCore
from qgis.utils import plugins

from pinta_qgis_plugin.utils import i18n_utils

if typing.TYPE_CHECKING:
    from pinta_qgis_plugin.plugin import Plugin

__version__ = "0.0.0"

TRANSLATORS: list[QtCore.QTranslator] = []


def classFactory(_):  # noqa: ANN201, ANN001, N802
    """Class factory."""
    TRANSLATORS.extend(i18n_utils.setup_all_translators())

    from pinta_qgis_plugin.plugin import Plugin  # noqa: PLC0415

    return Plugin()


def get_instance() -> "Plugin | None":
    """Get instance."""
    return plugins.get(__name__)
