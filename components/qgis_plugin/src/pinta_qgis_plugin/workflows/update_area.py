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

from pinta_qgis_plugin.api import api_client
from pinta_qgis_plugin.utils import messages


@messages.popup_if_fails
def start_dissolve_update_areas_workflow(production_area_id: str) -> None:
    """Starts a dissolve update areas workflow for the given production area."""
    api_client.get_api_client().start_dissolve_update_areas_workflow(production_area_id)
