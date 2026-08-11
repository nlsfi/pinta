# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os

import geopandas
import pytest
from pinta_common import MASK_OGR_ENV_PREFIX, Settings
from pinta_test_utils import pinta_utils

from pinta_processing import core, exceptions
from pinta_processing.reader import ogr

GPKG = "ogr/polygons.gpkg"
LAYER = "polygons"

# The file holds two 3D polygons around Helsinki, already in the project CRS.
EXPECTED_ROWS = 2
EXPECTED_ATTRIBUTES = ["bar", "baz"]
EXPECTED_BOUNDS = (384884.27, 6671370.26, 386300.27, 6672076.13)


@pytest.fixture
def gpkg_source() -> ogr.OgrSource:
    """The test GeoPackage as a source, whole file."""
    return ogr.OgrSource(str(pinta_utils.get_test_data_path(GPKG)))


@pytest.fixture(autouse=True)
def _clear_mask_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mask sources from the developer's environment out of the tests."""
    for variable in list(os.environ):
        if variable.startswith(MASK_OGR_ENV_PREFIX):
            monkeypatch.delenv(variable)


def test_reads_a_geopackage_from_test_data(gpkg_source: ogr.OgrSource) -> None:
    """A real GeoPackage on disk reads into the combined frame."""
    result = ogr.read_ogr_geodataframe([gpkg_source])

    assert isinstance(result, geopandas.GeoDataFrame)
    assert len(result) == EXPECTED_ROWS
    assert sorted(result["foo"].tolist()) == EXPECTED_ATTRIBUTES
    assert result.geometry.name == ogr.GEOMETRY_COLUMN
    assert result.crs == f"EPSG:{Settings.DB_SRID}"
    assert result.total_bounds == pytest.approx(EXPECTED_BOUNDS, abs=0.01)


def test_reads_the_named_layer(gpkg_source: ogr.OgrSource) -> None:
    """Naming the only layer gives the same result as reading the file whole."""
    named = ogr.OgrSource(gpkg_source.data_source, layer=LAYER)

    assert ogr.read_ogr_geodataframe([named]).equals(
        ogr.read_ogr_geodataframe([gpkg_source])
    )


def test_rows_record_the_layer_they_came_from(gpkg_source: ogr.OgrSource) -> None:
    """The layer name is discovered from the file, not configured."""
    result = ogr.read_ogr_geodataframe([gpkg_source])

    assert result[ogr.SOURCE_LAYER_NAME_COLUMN].tolist() == [LAYER] * EXPECTED_ROWS


def test_keeps_the_z_coordinate_of_3d_polygons(gpkg_source: ogr.OgrSource) -> None:
    """The polygons are 3D and must not be flattened on the way through."""
    result = ogr.read_ogr_geodataframe([gpkg_source])

    assert result.geometry.has_z.all()


def test_reprojects_the_geopackage_into_another_crs(
    gpkg_source: ogr.OgrSource,
) -> None:
    """The source is in the project CRS, so a different one must move it."""
    result = ogr.read_ogr_geodataframe([gpkg_source], crs="EPSG:4326")

    assert result.crs == "EPSG:4326"
    # Helsinki in degrees rather than TM35FIN metres.
    minx, miny, maxx, maxy = result.total_bounds
    assert minx == pytest.approx(24.9, abs=0.2)
    assert miny == pytest.approx(60.2, abs=0.2)
    assert maxx > minx
    assert maxy > miny


def test_combines_the_same_file_configured_twice(gpkg_source: ogr.OgrSource) -> None:
    """Several sources stack into one frame, in the order given."""
    result = ogr.read_ogr_geodataframe([gpkg_source, gpkg_source])

    assert len(result) == 2 * EXPECTED_ROWS
    assert result.crs == f"EPSG:{Settings.DB_SRID}"


def test_reads_the_geopackage_configured_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole configuration path, from environment variable to frame."""
    path = pinta_utils.get_test_data_path(GPKG)
    monkeypatch.setenv(f"{MASK_OGR_ENV_PREFIX}POLYGONS", str(path))

    sources = ogr.OgrReader.sources_from_environment()

    assert sources == [ogr.OgrSource(data_source=str(path), layer=None)]
    assert len(ogr.read_ogr_geodataframe(sources)) == EXPECTED_ROWS


def test_reads_the_layer_configured_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `|layername=` suffix reaches the reader as a parsed layer."""
    path = pinta_utils.get_test_data_path(GPKG)
    monkeypatch.setenv(
        f"{MASK_OGR_ENV_PREFIX}POLYGONS",
        f"{path}{ogr.LAYER_SEPARATOR}{LAYER}",
    )

    sources = ogr.OgrReader.sources_from_environment()

    assert sources == [ogr.OgrSource(data_source=str(path), layer=LAYER)]
    assert len(ogr.read_ogr_geodataframe(sources)) == EXPECTED_ROWS


def test_stage_reads_the_geopackage_into_a_vector_dataset(
    gpkg_source: ogr.OgrSource,
) -> None:
    result = ogr.OgrReader([gpkg_source]).process(None)

    assert isinstance(result, core.VectorDataset)
    assert len(result.geodataframe) == EXPECTED_ROWS
    assert result.geodataframe.crs == f"EPSG:{Settings.DB_SRID}"


def test_rejects_a_layer_the_geopackage_does_not_have(
    gpkg_source: ogr.OgrSource,
) -> None:
    missing = ogr.OgrSource(gpkg_source.data_source, layer="does_not_exist")

    with pytest.raises(exceptions.OgrSourceError, match="does_not_exist"):
        ogr.read_ogr_geodataframe([missing])
