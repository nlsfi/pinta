# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pathlib
import typing

import geopandas
import pandas as pd
import pyogrio
import pytest
from pinta_common import Settings
from shapely.geometry import Point, Polygon

from pinta_processing import core, exceptions
from pinta_processing.reader import ogr
from pinta_processing_test_utils import constants

_SQUARE = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
_OTHER_SQUARE = Polygon([(20, 20), (30, 20), (30, 30), (20, 30)])


def _write(
    path: pathlib.Path,
    frame: geopandas.GeoDataFrame,
    layer: str = "masks",
) -> ogr.OgrSource:
    """Write a frame as a GeoPackage layer and return it as a source."""
    frame.to_file(path, layer=layer)
    return ogr.OgrSource(str(path))


def _frame(
    geometries: list, crs: str | None = constants.DEFAULT_CRS, **attributes: typing.Any
) -> geopandas.GeoDataFrame:
    return geopandas.GeoDataFrame(attributes, geometry=geometries, crs=crs)


def test_reads_a_source_into_a_geodataframe(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE], name=["quarry"]))

    result = ogr.read_ogr_geodataframe([source])

    assert isinstance(result, geopandas.GeoDataFrame)
    assert len(result) == 1
    assert result["name"].tolist() == ["quarry"]
    assert result.geometry.iloc[0].equals(_SQUARE)


def test_geometry_column_is_named_geom(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE], name=["quarry"]))

    result = ogr.read_ogr_geodataframe([source])

    assert result.geometry.name == ogr.GEOMETRY_COLUMN


def test_reads_source_into_project_crs(tmp_path: pathlib.Path):
    # A point in Helsinki given in WGS 84, which must come out in the
    # project CRS as metric TM35FIN coordinates.
    source = _write(
        tmp_path / "wgs84.gpkg",
        _frame([Point(24.94, 60.17)], crs="EPSG:4326", name=["helsinki"]),
    )

    result = ogr.read_ogr_geodataframe([source])

    assert result.crs == f"EPSG:{Settings.DB_SRID}"
    point = result.geometry.iloc[0]
    assert point.x == pytest.approx(385_000, abs=5_000)
    assert point.y == pytest.approx(6_672_000, abs=5_000)


def test_reads_source_into_explicitly_given_crs(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE]))

    assert ogr.read_ogr_geodataframe([source], crs="EPSG:4326").crs == "EPSG:4326"


def test_combines_attributes_of_all_sources(tmp_path: pathlib.Path):
    quarries = _write(
        tmp_path / "quarries.gpkg", _frame([_SQUARE], name=["quarry"], depth=[12.5])
    )
    lakes = _write(
        tmp_path / "lakes.gpkg", _frame([_OTHER_SQUARE], name=["lake"], shore=["rocky"])
    )

    result = ogr.read_ogr_geodataframe([quarries, lakes])

    assert len(result) == 2
    assert set(result.columns) == {"name", "depth", "shore", ogr.GEOMETRY_COLUMN}


def test_attributes_missing_from_a_source_are_left_empty(tmp_path: pathlib.Path):
    quarries = _write(tmp_path / "quarries.gpkg", _frame([_SQUARE], depth=[12.5]))
    lakes = _write(tmp_path / "lakes.gpkg", _frame([_OTHER_SQUARE], shore=["rocky"]))

    result = ogr.read_ogr_geodataframe([quarries, lakes])

    assert result["depth"].isna().tolist() == [False, True]
    assert result["depth"].iloc[0] == 12.5
    assert result["shore"].isna().tolist() == [True, False]
    assert result["shore"].iloc[1] == "rocky"


def test_sources_are_read_in_the_order_given(tmp_path: pathlib.Path):
    first = _write(tmp_path / "first.gpkg", _frame([_SQUARE], name=["a"]))
    second = _write(tmp_path / "second.gpkg", _frame([_OTHER_SQUARE], name=["b"]))

    assert ogr.read_ogr_geodataframe([second, first])["name"].tolist() == ["b", "a"]


def test_reads_every_spatial_layer_when_no_layer_is_given(tmp_path: pathlib.Path):
    path = tmp_path / "masks.gpkg"
    _write(path, _frame([_SQUARE], name=["quarry"]), layer="quarries")
    source = _write(path, _frame([_OTHER_SQUARE], name=["lake"]), layer="lakes")

    result = ogr.read_ogr_geodataframe([source])

    assert sorted(result["name"].tolist()) == ["lake", "quarry"]


def test_reads_only_the_requested_layer(tmp_path: pathlib.Path):
    path = tmp_path / "masks.gpkg"
    _write(path, _frame([_SQUARE], name=["quarry"]), layer="quarries")
    _write(path, _frame([_OTHER_SQUARE], name=["lake"]), layer="lakes")

    result = ogr.read_ogr_geodataframe([ogr.OgrSource(str(path), "lakes")])

    assert result["name"].tolist() == ["lake"]


def test_returns_an_empty_frame_without_sources():
    result = ogr.read_ogr_geodataframe([])

    assert result.empty
    assert result.crs == f"EPSG:{Settings.DB_SRID}"
    assert result.geometry.name == ogr.GEOMETRY_COLUMN


def _write_attribute_table(path: pathlib.Path, layer: str) -> None:
    """Add a plain, geometry-less table to a GeoPackage."""
    pyogrio.write_dataframe(
        pd.DataFrame({"code": [1, 2], "label": ["a", "b"]}),
        path,
        layer=layer,
        driver="GPKG",
        append=path.exists(),
    )


def test_skips_attribute_tables_when_reading_every_layer(tmp_path: pathlib.Path):
    """A GeoPackage may hold plain tables next to its spatial layers."""
    path = tmp_path / "mixed.gpkg"
    source = _write(path, _frame([_SQUARE], name=["quarry"]), layer="quarries")
    _write_attribute_table(path, "codelist")

    result = ogr.read_ogr_geodataframe([source])

    assert result["name"].tolist() == ["quarry"]
    assert "code" not in result.columns


def test_rejects_a_named_attribute_table(tmp_path: pathlib.Path):
    """Naming a geometry-less layer is an error, not an AttributeError."""
    path = tmp_path / "mixed.gpkg"
    _write(path, _frame([_SQUARE]), layer="quarries")
    _write_attribute_table(path, "codelist")

    with pytest.raises(exceptions.OgrSourceError, match="no geometry"):
        ogr.read_ogr_geodataframe([ogr.OgrSource(str(path), layer="codelist")])


def test_rejects_a_source_with_only_attribute_tables(tmp_path: pathlib.Path):
    path = tmp_path / "tables.gpkg"
    _write_attribute_table(path, "codelist")

    with pytest.raises(exceptions.OgrSourceError, match="no layers with geometries"):
        ogr.read_ogr_geodataframe([ogr.OgrSource(str(path))])


def test_rejects_a_missing_file(tmp_path: pathlib.Path):
    source = ogr.OgrSource(str(tmp_path / "does-not-exist.gpkg"))

    with pytest.raises(exceptions.OgrSourceError, match="does-not-exist"):
        ogr.read_ogr_geodataframe([source])


def test_rejects_a_missing_layer(tmp_path: pathlib.Path):
    path = tmp_path / "masks.gpkg"
    _write(path, _frame([_SQUARE]), layer="quarries")

    with pytest.raises(exceptions.OgrSourceError):
        ogr.read_ogr_geodataframe([ogr.OgrSource(str(path), "lakes")])


def test_rejects_a_source_without_a_crs(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE], crs=None))

    with pytest.raises(exceptions.OgrSourceError, match="no CRS"):
        ogr.read_ogr_geodataframe([source])


def test_rejects_a_source_with_a_colliding_attribute_name(tmp_path: pathlib.Path):
    # GeoPackage reserves the name for its own geometry column, so an
    # attribute that collides can only come from another format.
    path = tmp_path / "masks.geojson"
    _frame([_SQUARE], crs="EPSG:4326", geom=["collides"]).to_file(path)

    with pytest.raises(exceptions.OgrSourceError, match="collides"):
        ogr.read_ogr_geodataframe([ogr.OgrSource(str(path))])


def test_stage_returns_the_sources_as_a_vector_dataset(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE], name=["quarry"]))

    result = ogr.OgrReader([source]).process(None)

    assert isinstance(result, core.VectorDataset)
    assert result.geodataframe["name"].tolist() == ["quarry"]
    assert result.geodataframe.crs == f"EPSG:{Settings.DB_SRID}"


def test_stage_passes_its_crs_on(tmp_path: pathlib.Path):
    source = _write(tmp_path / "masks.gpkg", _frame([_SQUARE]))

    result = ogr.OgrReader([source], crs="EPSG:4326").process(None)

    assert result.geodataframe.crs == "EPSG:4326"
