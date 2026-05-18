# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

if TYPE_CHECKING:
    from pinta_qgis_plugin.plugin import Plugin


def test_plugin_startup_adds_all_layers_to_project(
    qgis_plugin: "Plugin",
) -> None:
    from pinta_qgis_plugin.project.groups.basemap_layer_collection import (  # noqa: PLC0415
        BasemapLayerCollection,
    )
    from pinta_qgis_plugin.project.groups.dem_layer_collection import (  # noqa: PLC0415
        DemLayerCollection,
    )
    from pinta_qgis_plugin.project.groups.management_layer_collection import (  # noqa: PLC0415
        ManagementLayerCollection,
    )

    assert len(QgsProject.instance().mapLayers()) == 4

    basemap_layers = BasemapLayerCollection.get().find_layers()
    assert len(basemap_layers) == 1
    assert basemap_layers[0].name() == "OpenStreetMap"
    assert isinstance(basemap_layers[0], QgsRasterLayer)

    dem_layers = DemLayerCollection.get().find_layers()
    assert len(dem_layers) == 1
    assert dem_layers[0].name() == "Elevation model"
    assert isinstance(dem_layers[0], QgsRasterLayer)

    management_layers = ManagementLayerCollection.get().find_layers()
    assert len(management_layers) == 2
    management_layer_names = {layer.name() for layer in management_layers}
    assert management_layer_names == {"Production area", "Point cloud tile"}

    for layer in management_layers:
        assert isinstance(layer, QgsVectorLayer)
        assert layer.isValid()
        assert layer.featureCount() == 0
