# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import pathlib
import typing

import geopandas
import pandas as pd
import pyogrio
import pytest
from pinta_common import MASK_OGR_ENV_PREFIX, Settings
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
    assert set(result.columns) == {
        "name",
        "depth",
        "shore",
        ogr.GEOMETRY_COLUMN,
        ogr.SOURCE_LAYER_NAME_COLUMN,
    }


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


def test_each_row_records_the_layer_it_came_from(tmp_path: pathlib.Path):
    """Rows stay identifiable once several layers are concatenated."""
    path = tmp_path / "masks.gpkg"
    _write(path, _frame([_SQUARE], name=["quarry"]), layer="quarries")
    source = _write(path, _frame([_OTHER_SQUARE], name=["lake"]), layer="lakes")

    result = ogr.read_ogr_geodataframe([source])

    by_name = dict(
        zip(result["name"], result[ogr.SOURCE_LAYER_NAME_COLUMN], strict=True)
    )
    assert by_name == {"quarry": "quarries", "lake": "lakes"}


def test_layer_column_of_an_explicitly_named_layer(tmp_path: pathlib.Path):
    path = tmp_path / "masks.gpkg"
    _write(path, _frame([_SQUARE], name=["quarry"]), layer="quarries")
    _write(path, _frame([_OTHER_SQUARE], name=["lake"]), layer="lakes")

    result = ogr.read_ogr_geodataframe([ogr.OgrSource(str(path), "lakes")])

    assert result[ogr.SOURCE_LAYER_NAME_COLUMN].tolist() == ["lakes"]


def test_layer_column_distinguishes_rows_of_different_sources(tmp_path: pathlib.Path):
    """Two files whose layers are named differently stay apart."""
    quarries = _write(tmp_path / "a.gpkg", _frame([_SQUARE]), layer="quarries")
    lakes = _write(tmp_path / "b.gpkg", _frame([_OTHER_SQUARE]), layer="lakes")

    result = ogr.read_ogr_geodataframe([quarries, lakes])

    assert result[ogr.SOURCE_LAYER_NAME_COLUMN].tolist() == ["quarries", "lakes"]


def test_rejects_a_source_with_a_colliding_source_layer_attribute(
    tmp_path: pathlib.Path,
):
    source = _write(
        tmp_path / "masks.gpkg",
        _frame([_SQUARE], "EPSG:3067", **{ogr.SOURCE_LAYER_NAME_COLUMN: ["collides"]}),
    )

    with pytest.raises(exceptions.OgrSourceError, match="collides with the layer"):
        ogr.read_ogr_geodataframe([source])


def test_returns_an_empty_frame_without_sources():
    result = ogr.read_ogr_geodataframe([])

    assert result.empty
    assert result.crs == f"EPSG:{Settings.DB_SRID}"
    assert result.geometry.name == ogr.GEOMETRY_COLUMN
    # The columns every read produces, so consumers see a stable schema.
    assert ogr.SOURCE_LAYER_NAME_COLUMN in result.columns


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


@pytest.fixture(autouse=True)
def _clear_mask_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mask sources from the developer's environment out of the tests."""
    for variable in list(os.environ):
        if variable.startswith(MASK_OGR_ENV_PREFIX):
            monkeypatch.delenv(variable)


def _set_mask_source(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(f"{MASK_OGR_ENV_PREFIX}{name}", value)


def test_parse_ogr_source_splits_off_the_layer_suffix() -> None:
    parsed = ogr.parse_ogr_source(f" /input/finland.gpkg{ogr.LAYER_SEPARATOR}water ")

    assert parsed == ogr.OgrSource(data_source="/input/finland.gpkg", layer="water")


def test_parse_ogr_source_without_a_layer_suffix_has_no_layer() -> None:
    assert ogr.parse_ogr_source("/input/masks.gpkg").layer is None


@pytest.mark.parametrize(
    "data_source",
    [
        "OAPIF:https://demo.pygeoapi.io/master",
        "WFS:https://example.org/wfs?service=WFS&version=2.0.0",
        "https://example.org/masks.fgb",
        "/vsizip//input/masks.zip/masks.shp",
        "/vsicurl/https://example.org/masks.fgb",
        "GPKG:/input/masks.gpkg",
        # An OGC API - Features collection URL, which needs no layer suffix,
        # with the service's own query parameters.
        "OAPIF:https://example.org/collections/x?bbox=4,52,5,53&limit=1000",
    ],
)
def test_parse_ogr_source_keeps_the_data_source_verbatim(data_source: str) -> None:
    """GDAL connection strings must survive parsing, unlike filesystem paths."""
    assert ogr.parse_ogr_source(data_source) == ogr.OgrSource(
        data_source=data_source, layer=None
    )
    assert ogr.parse_ogr_source(
        f"{data_source}{ogr.LAYER_SEPARATOR}masks"
    ) == ogr.OgrSource(data_source=data_source, layer="masks")


def test_parse_ogr_source_rejects_an_empty_layer_name() -> None:
    with pytest.raises(exceptions.OgrSourceError, match="layer name"):
        ogr.parse_ogr_source(f"/input/masks.gpkg{ogr.LAYER_SEPARATOR}")


def test_sources_from_environment_collects_prefixed_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_mask_source(monkeypatch, "QUARRIES", "/input/quarries.gpkg")
    _set_mask_source(monkeypatch, "WATER", "/input/finland.gpkg|layername=water")

    assert ogr.OgrReader.sources_from_environment() == [
        ogr.OgrSource(data_source="/input/quarries.gpkg", layer=None),
        ogr.OgrSource(data_source="/input/finland.gpkg", layer="water"),
    ]


def test_sources_from_environment_is_ordered_by_variable_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_mask_source(monkeypatch, "ZZZ", "/input/last.gpkg")
    _set_mask_source(monkeypatch, "AAA", "/input/first.gpkg")

    assert [
        source.data_source for source in ogr.OgrReader.sources_from_environment()
    ] == ["/input/first.gpkg", "/input/last.gpkg"]


def test_sources_from_environment_ignores_other_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PINTA_PROCESSING_OTHER_SETTING", "/input/nope.gpkg")
    monkeypatch.setenv("MASK_OGR_QUARRIES", "/input/nope.gpkg")

    assert ogr.OgrReader.sources_from_environment() == []


def test_sources_from_environment_skips_empty_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_mask_source(monkeypatch, "QUARRIES", "/input/quarries.gpkg")
    _set_mask_source(monkeypatch, "WATER", "   ")

    assert ogr.OgrReader.sources_from_environment() == [
        ogr.OgrSource(data_source="/input/quarries.gpkg", layer=None)
    ]


def test_sources_from_environment_ignores_other_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_mask_source(monkeypatch, "QUARRIES", "/input/quarries.gpkg")
    monkeypatch.setenv("PINTA_PROCESSING_CLIP_OGR_AREAS", "/input/clip.gpkg")

    assert ogr.OgrReader.sources_from_environment() == [
        ogr.OgrSource(data_source="/input/quarries.gpkg", layer=None)
    ]
