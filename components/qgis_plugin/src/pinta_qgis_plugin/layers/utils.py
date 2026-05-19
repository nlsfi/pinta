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

from qgis.core import QgsMapLayer


def set_field_aliases(layer: QgsMapLayer, aliases: dict[str, str]) -> None:
    """Set field aliases for layer types that expose QGIS field alias APIs."""
    if (
        not aliases
        or not hasattr(layer, "fields")
        or not hasattr(layer, "setFieldAlias")
    ):
        return

    fields = layer.fields()
    for field_name, alias in aliases.items():
        field_index = fields.lookupField(field_name)
        if field_index >= 0:
            layer.setFieldAlias(field_index, alias)
