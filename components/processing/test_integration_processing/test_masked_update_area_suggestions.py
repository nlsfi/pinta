# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pathlib
import typing

import affine
import geopandas
import numpy as np
import pytest
import shapely
from geoalchemy2.shape import to_shape
from pinta_common import Settings
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from pinta_db_utils.postgis import raster
from sqlmodel import select

from pinta_processing import core, writer
from pinta_processing.reader import ogr
from pinta_processing.scripts import masked_update_area_suggestions
from pinta_processing.utils import tiles

if typing.TYPE_CHECKING:
    from sqlmodel import Session

_PIXEL_SIZE = float(Settings.DB_DEM_PIXEL_SIZE)
_TILE_SPAN = Settings.DB_DEFAULT_TILE_SIZE * _PIXEL_SIZE
# Anchored on the global tile grid so the test raster lands in a single tile.
_LEFT = tiles.GRID_ORIGIN_X
_TOP = tiles.GRID_ORIGIN_Y + _TILE_SPAN

_ROWS = 20
_HALF_COLUMNS = 20
_BOTTOM = _TOP - _ROWS * _PIXEL_SIZE
# The left half of the raster is flat, the right half rises column by column.
_FLAT_AREA = shapely.box(_LEFT + 4, _BOTTOM + 4, _LEFT + 36, _TOP - 4)
_UNEVEN_AREA = shapely.box(_LEFT + 44, _BOTTOM + 4, _LEFT + 76, _TOP - 4)
# Inside the same raster tile, but past the data: nodata all the way.
_NODATA_AREA = shapely.box(_LEFT + 200, _BOTTOM + 4, _LEFT + 250, _TOP - 4)

_WATER_LEVEL = 100.5


def _write_primary_dem(admin_primary_session: "Session") -> None:
    """Write a raster that is flat on its left half and uneven on its right."""
    flat = np.ones((_ROWS, _HALF_COLUMNS), dtype=np.float32)
    uneven = np.tile(np.arange(_HALF_COLUMNS, dtype=np.float32), (_ROWS, 1))
    dataset = core.RasterDataset(
        array=np.hstack((flat, uneven)),
        transform=affine.Affine(_PIXEL_SIZE, 0.0, _LEFT, 0.0, -_PIXEL_SIZE, _TOP),
        crs=f"EPSG:{Settings.DB_SRID}",
        nodata=Settings.DB_DEM_NODATA,
    )

    schema, table = model_utils.schema_and_table(dem.Dem)
    raster.initialize_raster_table(admin_primary_session, schema, table)
    writer.RasterPostgisWriter(schema, table, admin_primary_session).process(dataset)


def _lake_source(
    path: pathlib.Path, *geometries: shapely.Polygon
) -> list[ogr.OgrSource]:
    """Write the geometries as a lake part source with only a surveyed level."""
    geopandas.GeoDataFrame(
        {
            "average_water_level": [None] * len(geometries),
            "surveyed_water_level": [_WATER_LEVEL] * len(geometries),
        },
        geometry=list(geometries),
        crs=f"EPSG:{Settings.DB_SRID}",
    ).to_file(path, layer="lake_part")
    return [ogr.OgrSource(str(path))]


def _mask_polygon(geometry: shapely.Polygon) -> dict[str, typing.Any]:
    return {"geom_wkt": geometry.wkt, "elevation": 0.12, "source_layer": "sea_part"}


def _suggestions(session: "Session") -> list[reference.UpdateAreaSuggestion]:
    session.expire_all()
    return list(session.exec(select(reference.UpdateAreaSuggestion)).all())


def test_uneven_mask_is_suggested_as_an_update_area(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
    tmp_path: pathlib.Path,
) -> None:
    _write_primary_dem(admin_primary_session)
    sources = _lake_source(tmp_path / "masks.gpkg", _UNEVEN_AREA)

    suggestions = (
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            session, processing_worker_session, sources
        )
    )

    assert len(suggestions) == 1
    stored = _suggestions(processing_worker_session)
    assert len(stored) == 1
    # The source carries no average water level, so the surveyed one wins.
    assert stored[0].elevation == _WATER_LEVEL
    assert to_shape(stored[0].geom).equals(_UNEVEN_AREA)


def test_flat_mask_is_not_suggested(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
    tmp_path: pathlib.Path,
) -> None:
    _write_primary_dem(admin_primary_session)
    sources = _lake_source(tmp_path / "masks.gpkg", _FLAT_AREA)

    suggestions = (
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            session, processing_worker_session, sources
        )
    )

    assert suggestions == []
    assert _suggestions(processing_worker_session) == []


def test_masks_outside_the_area_of_interest_are_left_alone(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
    tmp_path: pathlib.Path,
) -> None:
    # The uneven mask would be suggested, but it falls outside the production
    # area, and the nodata one is never read at all.
    _write_primary_dem(admin_primary_session)
    sources = _lake_source(tmp_path / "masks.gpkg", _UNEVEN_AREA, _NODATA_AREA)

    suggestions = (
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            session,
            processing_worker_session,
            sources,
            area_of_interest=_FLAT_AREA.wkt,
        )
    )

    assert suggestions == []
    assert _suggestions(processing_worker_session) == []


def test_nothing_is_stored_when_a_mask_has_only_nodata_in_the_dem(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
    tmp_path: pathlib.Path,
) -> None:
    # The second mask falls inside a written tile, but every pixel of it is
    # nodata, so the whole batch is left out.
    _write_primary_dem(admin_primary_session)
    sources = _lake_source(tmp_path / "masks.gpkg", _UNEVEN_AREA, _NODATA_AREA)

    with pytest.raises(ValueError, match=r"no elevations in dem\.dem"):
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            session, processing_worker_session, sources
        )

    # The suggestion with data is inserted
    assert len(_suggestions(processing_worker_session)) == 1


def test_mask_outside_the_dem_tiles_fails(
    admin_primary_session: "Session",
    session: "Session",
) -> None:
    _write_primary_dem(admin_primary_session)
    far_away = shapely.box(_LEFT + 10_000, _TOP + 10_000, _LEFT + 10_100, _TOP + 10_100)

    with pytest.raises(ValueError, match=r"No raster data found in dem\.dem"):
        masked_update_area_suggestions.build_update_area_suggestions(
            session, **_mask_polygon(far_away)
        )


def test_reads_the_elevations_of_a_multi_layer_geopackage(
    tmp_path: pathlib.Path,
) -> None:
    """Layer names and attributes come straight out of GDAL, not from config."""
    path = tmp_path / "masks.gpkg"
    lakes = geopandas.GeoDataFrame(
        {"average_water_level": [80.5]},
        geometry=[shapely.box(0, 0, 10, 10)],
        crs=f"EPSG:{Settings.DB_SRID}",
    )
    sea = geopandas.GeoDataFrame(
        geometry=[shapely.box(20, 20, 30, 30)], crs=f"EPSG:{Settings.DB_SRID}"
    )
    lakes.to_file(path, layer="lake_part")
    sea.to_file(path, layer="sea_part")

    polygons = masked_update_area_suggestions.find_mask_polygons(
        [ogr.OgrSource(str(path))]
    )

    assert sorted(
        (polygon["source_layer"], polygon["elevation"]) for polygon in polygons
    ) == [
        ("lake_part", 80.5),
        ("sea_part", masked_update_area_suggestions.SEA_PART_ELEVATION),
    ]
