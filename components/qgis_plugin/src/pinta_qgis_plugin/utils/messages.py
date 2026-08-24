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

import functools
import logging
import typing

from qgis.PyQt.QtWidgets import QMessageBox, QWidget
from qgis.utils import iface as utils_iface
from qgis_plugin_tools.tools.exceptions import QgsPluginException
from qgis_plugin_tools.tools.i18n import tr

if typing.TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = typing.cast("QgisInterface", utils_iface)

LOGGER = logging.getLogger(__name__)


def popup_if_fails(function: typing.Callable) -> typing.Callable:
    """Show error dialog if execution fails."""

    # TODO: correct signature
    @functools.wraps(function)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:  # noqa: ANN401
        try:
            return function(*args, **kwargs)
        except QgsPluginException as e:
            title = e.message or tr("Error occurred")
            body = f"{title}\n\n{e.bar_msg.get('details', '')}"
            show_error_dialog(title, body)
        except Exception:
            title = tr("Unhandled exception occurred")
            body = tr(
                "An unhandled exception occurred. Check the log for more details."
            )
            LOGGER.exception(title)
            show_error_dialog(title, body)

    return wrapper


def show_error_dialog(
    title: str,
    message: str,
    parent: QWidget | None = None,
    icon: QMessageBox.Icon = QMessageBox.Icon.Critical,
) -> None:
    """Show error dialog."""
    LOGGER.error("%s: %s", title, message)
    message_box = QMessageBox(parent or iface.mainWindow())
    message_box.setWindowTitle(title)
    message_box.setText(message)
    message_box.setIcon(icon)
    message_box.setStandardButtons(QMessageBox.Ok)
    message_box.setDefaultButton(QMessageBox.Ok)
    message_box.show()
    # activate indicates need for input if created while focus is outside qgis
    message_box.activateWindow()
    message_box.exec()


def ask_confirmation(
    title: str,
    message: str,
    parent: QWidget | None = None,
) -> bool:
    """Ask the user to confirm an action. Return True when confirmed."""
    message_box = QMessageBox(parent or iface.mainWindow())
    message_box.setWindowTitle(title)
    message_box.setText(message)
    message_box.setIcon(QMessageBox.Icon.Warning)
    message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    message_box.setDefaultButton(QMessageBox.No)
    message_box.show()
    message_box.activateWindow()
    return message_box.exec() == QMessageBox.Yes
