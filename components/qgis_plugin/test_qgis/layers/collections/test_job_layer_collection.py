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

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes

from pinta_qgis_plugin import exceptions
from pinta_qgis_plugin.layers import config
from pinta_qgis_plugin.project.groups import job_layer_collection


@pytest.fixture
def layer_collection() -> job_layer_collection.JobLayerCollection:
    return job_layer_collection.JobLayerCollection()


@pytest.fixture
def vector_config() -> config.VectorLayerConfig:
    return config.VectorLayerConfig(
        schema="reference",
        table_name="diff_polygon",
        layer_name="Polygonized DEM difference",
        layer_id="polygonized_dem_diff",
        key_column="id",
        wkb_type=QgsWkbTypes.Polygon,
    )


@pytest.fixture
def raster_config() -> config.RasterLayerConfig:
    return config.RasterLayerConfig(
        schema="reference",
        table_name="dem",
        layer_name="Reference DEM",
        layer_id="reference_dem",
    )


@pytest.fixture
def vector_job_layer(empty_multipolygon_layer: QgsVectorLayer) -> QgsVectorLayer:
    layer = empty_multipolygon_layer
    layer.setName("Polygonized DEM difference")
    return layer


@pytest.fixture
def raster_job_layer(empty_raster_layer: QgsRasterLayer) -> QgsRasterLayer:
    layer = empty_raster_layer
    layer.setName("Reference DEM")
    return layer


@pytest.fixture
def mock_qgs_project(mocker: MockerFixture) -> MagicMock:
    mock_project = MagicMock()
    mock_project.mapLayers.return_value = {}
    mocker.patch.object(
        QgsProject,
        "instance",
        autospec=True,
        return_value=mock_project,
    )
    return mock_project


def test_add_to_project_requires_database_name(
    layer_collection: job_layer_collection.JobLayerCollection,
):
    with pytest.raises(exceptions.LayerCreationError, match="Database name"):
        layer_collection.add_to_project()


def test_set_database_name_sets_database_name_and_collection_id(
    layer_collection: job_layer_collection.JobLayerCollection,
):
    layer_collection.set_database_name("production_area_db")

    assert layer_collection.database_name == "production_area_db"
    assert layer_collection.collection_id == "job_production_area_db"


def test_add_to_project_adds_vector_and_raster_layers(
    layer_collection: job_layer_collection.JobLayerCollection,
    vector_config: config.VectorLayerConfig,
    raster_config: config.RasterLayerConfig,
    vector_job_layer: QgsVectorLayer,
    raster_job_layer: QgsRasterLayer,
    mock_qgs_project: MagicMock,
    mocker: MockerFixture,
):
    mocker.patch.object(
        job_layer_collection.job_layers,
        "LAYERS",
        [vector_config, raster_config],
    )
    mock_uri = mocker.MagicMock()
    mock_get_job_database_uri = mocker.patch.object(
        job_layer_collection.database,
        "get_job_database_uri",
        autospec=True,
        return_value=mock_uri,
    )
    mock_create_vector = mocker.patch.object(
        job_layer_collection.vector_layer,
        "create_vector_layer",
        autospec=True,
        return_value=vector_job_layer,
    )
    mock_create_raster = mocker.patch.object(
        job_layer_collection.raster_layer,
        "create_postgis_raster_layer",
        autospec=True,
        return_value=raster_job_layer,
    )
    group = mocker.MagicMock()
    mock_add_group = mocker.patch.object(
        layer_collection,
        "add_group_to_project",
        autospec=True,
        return_value=group,
    )

    layer_collection.set_database_name("production_area_db")
    layer_collection.set_group_name("group_name")
    layer_collection.add_to_project()

    mock_create_raster.assert_called_once_with(
        raster_config,
        job_layer_collection.RASTER_PROVIDER,
        mock_uri,
    )
    mock_create_vector.assert_called_once_with(
        vector_config,
        job_layer_collection.VECTOR_PROVIDER,
        mock_uri,
    )
    assert mock_get_job_database_uri.call_count == 2
    mock_get_job_database_uri.assert_called_with("production_area_db")
    mock_add_group.assert_called_once_with()
    group.setName.assert_called_once_with("group_name")
    assert group.addLayer.call_count == 2
    assert mock_qgs_project.addMapLayer.call_count == 2
    assert (
        vector_job_layer.customProperty(layer_collection.COLLECTION_ID_KEY)
        == layer_collection.collection_id
    )
    assert (
        raster_job_layer.customProperty(layer_collection.COLLECTION_ID_KEY)
        == layer_collection.collection_id
    )


def test_add_to_project_removes_existing_job_layers_before_adding(
    layer_collection: job_layer_collection.JobLayerCollection,
    vector_config: config.VectorLayerConfig,
    vector_job_layer: QgsVectorLayer,
    mock_qgs_project: MagicMock,
    mocker: MockerFixture,
):
    existing_layer = MagicMock()
    existing_layer.customProperty.return_value = layer_collection.collection_id
    mock_qgs_project.mapLayers.return_value = {"existing": existing_layer}
    mocker.patch.object(job_layer_collection.job_layers, "LAYERS", [vector_config])
    mocker.patch.object(
        job_layer_collection.database,
        "get_job_database_uri",
        autospec=True,
        return_value=mocker.MagicMock(),
    )
    mocker.patch.object(
        job_layer_collection.vector_layer,
        "create_vector_layer",
        autospec=True,
        return_value=vector_job_layer,
    )
    mocker.patch.object(
        layer_collection,
        "add_group_to_project",
        autospec=True,
        return_value=mocker.MagicMock(),
    )

    layer_collection.set_database_name("production_area_db")
    layer_collection.set_group_name("group_name")
    existing_layer.customProperty.return_value = layer_collection.collection_id
    layer_collection.add_to_project()

    mock_qgs_project.removeMapLayer.assert_called_once_with(existing_layer)


def test_remove_all_from_project_removes_all_job_groups_and_layers(
    mock_qgs_project: MagicMock,
    mocker: MockerFixture,
):
    root = mocker.MagicMock()
    mock_qgs_project.layerTreeRoot.return_value = root
    job_group = mocker.MagicMock()
    job_group.customProperty.return_value = "job_production_area"
    job_parent = mocker.MagicMock()
    job_group.parent.return_value = job_parent
    other_job_group = mocker.MagicMock()
    other_job_group.customProperty.return_value = "job_other_production_area"
    other_job_parent = mocker.MagicMock()
    other_job_group.parent.return_value = other_job_parent
    management_group = mocker.MagicMock()
    management_group.customProperty.return_value = "management"
    root.findGroups.return_value = [job_group, management_group, other_job_group]

    job_layer = mocker.MagicMock()
    job_layer.customProperty.return_value = "job_production_area"
    other_job_layer = mocker.MagicMock()
    other_job_layer.customProperty.return_value = "job_other_production_area"
    management_layer = mocker.MagicMock()
    management_layer.customProperty.return_value = "management"
    mock_qgs_project.mapLayers.return_value = {
        "job": job_layer,
        "other_job": other_job_layer,
        "management": management_layer,
    }

    job_layer_collection.JobLayerCollection.remove_all_from_project()

    mock_qgs_project.removeMapLayer.assert_any_call(job_layer)
    mock_qgs_project.removeMapLayer.assert_any_call(other_job_layer)
    assert mock_qgs_project.removeMapLayer.call_count == 2
    job_parent.removeChildNode.assert_called_once_with(job_group)
    other_job_parent.removeChildNode.assert_called_once_with(other_job_group)
