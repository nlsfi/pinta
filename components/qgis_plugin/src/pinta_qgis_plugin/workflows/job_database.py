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

from qgis_plugin_tools.tools.i18n import tr

from pinta_qgis_plugin.api import api_client
from pinta_qgis_plugin.project import manager
from pinta_qgis_plugin.utils import messages


@messages.popup_if_fails
def delete_job_database(production_area_id: str, database_name: str = "") -> None:
    """Delete the job database of the production area after a confirmation."""
    if not messages.ask_confirmation(
        tr("Delete production area database"),
        tr(
            "The database of the production area and all data in it are deleted "
            "permanently, and the processing status of the production area is reset. "
            "Do you want to continue?"
        ),
    ):
        return

    api_client.get_api_client().delete_job_database(production_area_id)
    if database_name:
        manager.close_production_area(database_name)
