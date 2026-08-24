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
from qgis_plugin_tools.tools import custom_logging
from qgis_plugin_tools.tools.exceptions import QgsPluginException
from qgis_plugin_tools.tools.i18n import tr


class LayerCreationError(QgsPluginException):
    def __init__(self, layer_name: str) -> None:
        super().__init__(
            f"Layer creation error: {layer_name}",
        )


class EnvironmentVariableError(QgsPluginException):
    def __init__(self, env_variable_name: str) -> None:
        super().__init__(
            f"Environment configuration error: {env_variable_name}",
        )


class PintaApiError(QgsPluginException):
    def __init__(self, message: str, details: str) -> None:
        super().__init__(
            message,
            bar_msg=custom_logging.bar_msg(details=details),
        )


class ApiConnectionError(PintaApiError):
    def __init__(self, conn_error: Exception) -> None:
        super().__init__(
            tr("Could not connect to API (is api running?)"),
            details=tr("Error was: {}", conn_error),
        )


class WorkflowNotStartedError(PintaApiError):
    def __init__(self, message: str, details: str) -> None:
        super().__init__(message, details)


class JobDatabaseNotDeletedError(PintaApiError):
    def __init__(self, message: str, details: str) -> None:
        super().__init__(message, details)
