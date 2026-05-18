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


from qgis.core import QgsDataSourceUri

from pinta_qgis_plugin import env


def get_database_uri() -> QgsDataSourceUri:
    """Get QgsDataSourceUri from environment variables."""
    uri = QgsDataSourceUri()
    uri.setConnection(
        env.PINTA_DB_HOST,
        env.PINTA_DB_PORT,
        env.PINTA_DB_NAME,
        env.PINTA_DB_EDITOR_USER,
        env.PINTA_DB_EDITOR_PASSWORD,
    )

    return uri
