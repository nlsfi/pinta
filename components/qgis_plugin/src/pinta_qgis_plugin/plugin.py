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
import logging
import typing

import qgis_plugin_tools
from qgis.utils import iface as utils_iface
from qgis_plugin_tools.tools import custom_logging
from qgis_plugin_tools.tools.i18n import tr

import pinta_qgis_plugin
from pinta_qgis_plugin.utils import i18n_utils

if typing.TYPE_CHECKING:
    from qgis.gui import QgisInterface

LOGGER = logging.getLogger(__name__)

iface = typing.cast("QgisInterface", utils_iface)


class Plugin:
    """QGIS Plugin Implementation."""

    def __init__(self) -> None:
        self._teardown_loggers = lambda: None
        self.translators = i18n_utils.setup_all_translators()

    def initGui(self) -> None:  # noqa: N802
        """Init gui."""
        global iface  # noqa: PLW0602

        iface.messageBar().pushMessage(
            "Info",
            tr("Hello from Pinta!"),
        )

        self._teardown_loggers = custom_logging.setup_loggers(
            pinta_qgis_plugin.__name__,
            qgis_plugin_tools.__name__,
            message_log_name=tr("Pinta plugin"),
        )

    def unload(self) -> None:
        """Unload plugin."""
        self._teardown_loggers()
        self._teardown_loggers = lambda: None
