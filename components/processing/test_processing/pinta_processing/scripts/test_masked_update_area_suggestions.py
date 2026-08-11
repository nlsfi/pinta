# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from unittest.mock import MagicMock

import geopandas
import numpy as np
import pytest
from pinta_common import Settings
from pinta_db.job_db.models import reference
from pytest_mock import MockerFixture
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from pinta_processing import core, reader
from pinta_processing.reader import ogr
from pinta_processing.scripts import masked_update_area_suggestions
from pinta_processing_test_utils import constants

_LAKE = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
_FAR_AWAY_LAKE = Polygon([(1000, 1000), (1010, 1000), (1010, 1010), (1000, 1010)])
_PRODUCTION_AREA = Polygon([(-5, -5), (20, -5), (20, 20), (-5, 20)])


def _source_frame(
    geometries: list, layers: list[str], **attributes: typing.Any
) -> geopandas.GeoDataFrame:
    """Build a frame shaped like the combined OGR reader output."""
    frame = geopandas.GeoDataFrame(
        {**attributes, ogr.SOURCE_LAYER_NAME_COLUMN: layers},
        geometry=geopandas.GeoSeries(geometries, crs=constants.DEFAULT_CRS),
        crs=constants.DEFAULT_CRS,
    )
    return frame.rename_geometry(ogr.GEOMETRY_COLUMN)


def _mock_sources(mocker: MockerFixture, frame: geopandas.GeoDataFrame) -> MagicMock:
    return mocker.patch(
        "pinta_processing.reader.read_ogr_geodataframe", return_value=frame
    )


def _polygon(
    source_layer: str = "lake_part", elevation: float = 80.5
) -> dict[str, typing.Any]:
    return {
        "geom_wkt": _LAKE.wkt,
        "elevation": elevation,
        "source_layer": source_layer,
    }


def _mock_dem(mocker: MockerFixture, array: np.ndarray) -> MagicMock:
    """Make the primary DEM read return the given pixel values."""
    postgis_reader = mocker.patch("pinta_processing.reader.PostgisReader")
    postgis_reader.return_value.process.return_value = core.RasterDataset(
        array=array,
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )
    return postgis_reader


def test_lake_polygon_takes_the_average_water_level(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame(
            [_LAKE],
            ["lake_part"],
            average_water_level=[80.5],
            surveyed_water_level=[81.5],
        ),
    )

    polygons = masked_update_area_suggestions.find_mask_polygons([])

    assert len(polygons) == 1
    assert polygons[0]["elevation"] == 80.5
    assert polygons[0]["source_layer"] == "lake_part"


def test_lake_polygon_falls_back_to_the_surveyed_water_level(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame(
            [_LAKE],
            ["lake_part"],
            average_water_level=[None],
            surveyed_water_level=[81.5],
        ),
    )

    assert masked_update_area_suggestions.find_mask_polygons([])[0]["elevation"] == 81.5


def test_sea_polygon_gets_the_fixed_sea_elevation(mocker: MockerFixture):
    # The sources carry no sea level, so the sea surface is modelled at a
    # fixed elevation.
    _mock_sources(mocker, _source_frame([_LAKE], ["sea_part"]))

    polygons = masked_update_area_suggestions.find_mask_polygons([])

    assert polygons[0]["elevation"] == masked_update_area_suggestions.SEA_PART_ELEVATION


def test_lake_polygon_without_a_water_level_is_skipped(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame(
            [_LAKE],
            ["lake_part"],
            average_water_level=[None],
            surveyed_water_level=[None],
        ),
    )

    assert masked_update_area_suggestions.find_mask_polygons([]) == []


def test_polygon_of_an_unknown_layer_is_skipped(mocker: MockerFixture):
    # Only lakes and the sea have an elevation rule.
    _mock_sources(mocker, _source_frame([_LAKE], ["quarry"], elevation=[10.0]))

    assert masked_update_area_suggestions.find_mask_polygons([]) == []


def test_non_polygon_geometry_is_skipped(mocker: MockerFixture):
    _mock_sources(mocker, _source_frame([Point(0, 0)], ["sea_part"]))

    assert masked_update_area_suggestions.find_mask_polygons([]) == []


def test_only_polygons_and_multipolygons_are_kept(mocker: MockerFixture):
    # A mask can be a polygon or a multi part one, everything else in the
    # source has no surface to flatten.
    _mock_sources(
        mocker,
        _source_frame(
            [
                _LAKE,
                MultiPolygon([_FAR_AWAY_LAKE]),
                LineString([(0, 0), (10, 10)]),
                Point(0, 0),
                None,
            ],
            ["sea_part"] * 5,
        ),
    )

    polygons = masked_update_area_suggestions.find_mask_polygons([])

    assert [polygon["geom_wkt"] for polygon in polygons] == [
        _LAKE.wkt,
        _FAR_AWAY_LAKE.wkt,
    ]


def test_multi_part_masks_are_split_into_single_polygons(mocker: MockerFixture):
    # Suggestions are stored as single polygons.
    _mock_sources(
        mocker,
        _source_frame([MultiPolygon([_LAKE, _FAR_AWAY_LAKE])], ["sea_part"]),
    )

    polygons = masked_update_area_suggestions.find_mask_polygons([])

    assert len(polygons) == 2
    assert all(polygon["geom_wkt"].startswith("POLYGON (") for polygon in polygons), (
        polygons
    )


def test_polygons_outside_the_clip_geometry_are_dropped(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame([_LAKE, _FAR_AWAY_LAKE], ["sea_part", "sea_part"]),
    )

    polygons = masked_update_area_suggestions.find_mask_polygons(
        [], area_of_interest=_PRODUCTION_AREA.wkt
    )

    assert len(polygons) == 1
    assert polygons[0]["geom_wkt"] == _LAKE.wkt


def test_z_coordinates_are_dropped_from_the_polygon(mocker: MockerFixture):
    # The sources may hold 3D polygons, the suggestion table holds 2D ones.
    lake_3d = Polygon([(0, 0, 5), (10, 0, 5), (10, 10, 5), (0, 10, 5)])
    _mock_sources(mocker, _source_frame([lake_3d], ["sea_part"]))

    assert (
        masked_update_area_suggestions.find_mask_polygons([])[0]["geom_wkt"]
        == _LAKE.wkt
    )


def test_the_given_sources_are_read_as_one_dataset(mocker: MockerFixture):
    read = _mock_sources(mocker, _source_frame([_LAKE], ["sea_part"]))
    sources = [reader.OgrSource("/input/lakes.gpkg"), reader.OgrSource("/input/sea")]

    masked_update_area_suggestions.find_mask_polygons(sources)

    assert read.call_args.args[0] == sources


def test_uneven_dem_is_suggested_as_an_update_area(mocker: MockerFixture):
    _mock_dem(mocker, np.array([[1.0, 1.0], [1.0, 1.5]], dtype=np.float32))

    suggestion = masked_update_area_suggestions.build_update_area_suggestions(
        MagicMock(), **_polygon()
    )

    assert isinstance(suggestion, reference.UpdateAreaSuggestion)
    assert suggestion.elevation == 80.5
    # The geometry column needs the CRS, which plain WKT does not carry.
    assert suggestion.geom == f"SRID={Settings.DB_SRID};{_LAKE.wkt}"


def test_elevations_are_read_from_the_primary_dem(mocker: MockerFixture):
    postgis_reader = _mock_dem(mocker, np.array([[1.0, 1.5]], dtype=np.float32))
    primary_session = MagicMock()

    masked_update_area_suggestions.build_update_area_suggestions(
        primary_session, **_polygon()
    )

    schema, table, session, wkt = postgis_reader.call_args.args
    assert (schema, table) == ("dem", "dem")
    assert session is primary_session
    assert wkt == _LAKE.wkt


def test_flat_dem_is_not_suggested(mocker: MockerFixture):
    _mock_dem(mocker, np.full((2, 2), 1.0, dtype=np.float32))

    assert (
        masked_update_area_suggestions.build_update_area_suggestions(
            MagicMock(), **_polygon()
        )
        is None
    )


def test_pixels_outside_the_polygon_do_not_make_the_surface_uneven(
    mocker: MockerFixture,
):
    # The read is clipped to the polygon, so everything outside it is nodata
    # and must not count as a differing elevation.
    _mock_dem(
        mocker,
        np.array([[1.0, constants.DEFAULT_NODATA], [1.0, 1.0]], dtype=np.float32),
    )
    assert (
        masked_update_area_suggestions.build_update_area_suggestions(
            MagicMock(), **_polygon()
        )
        is None
    )


def test_polygon_with_only_nodata_in_the_dem_fails(mocker: MockerFixture):
    # The masks are clipped to the production area, so a mask without any DEM
    # elevations means the DEM is missing data it should have.
    _mock_dem(mocker, np.full((2, 2), constants.DEFAULT_NODATA, np.float32))

    with pytest.raises(ValueError, match=r"no elevations in dem\.dem"):
        masked_update_area_suggestions.build_update_area_suggestions(
            MagicMock(), **_polygon()
        )


def test_polygon_outside_the_dem_tiles_fails(mocker: MockerFixture):
    # The reader raises when no raster tile intersects the polygon at all.
    postgis_reader = mocker.patch("pinta_processing.reader.PostgisReader")
    postgis_reader.return_value.process.side_effect = ValueError(
        "No raster data found in dem.dem for the given clipping geometry"
    )

    with pytest.raises(ValueError, match="No raster data found"):
        masked_update_area_suggestions.build_update_area_suggestions(
            MagicMock(), **_polygon()
        )


@pytest.mark.parametrize(
    ("elevations", "tolerance", "expected"),
    [
        ([1.0, 1.0, 1.0], 0.0, True),
        ([1.0, 1.0, 1.01], 0.0, False),
        ([1.0, 1.0, 1.01], 0.05, True),
    ],
)
def test_is_flat(elevations: list[float], tolerance: float, expected: bool):
    assert (
        masked_update_area_suggestions.is_flat(
            np.array(elevations, dtype=np.float32), tolerance
        )
        is expected
    )


def test_every_uneven_mask_is_inserted_in_one_batch(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame([_LAKE, _FAR_AWAY_LAKE], ["sea_part", "sea_part"]),
    )
    _mock_dem(mocker, np.array([[1.0, 1.5]], dtype=np.float32))
    job_session = MagicMock()

    suggestions = (
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            MagicMock(), job_session, []
        )
    )

    assert len(suggestions) == 2
    # One batch, so a mask that cannot be checked leaves nothing behind.
    job_session.add_all.assert_called_once_with(suggestions)
    job_session.commit.assert_called_once_with()


def test_flat_masks_are_left_out_of_the_batch(mocker: MockerFixture):
    _mock_sources(mocker, _source_frame([_LAKE], ["sea_part"]))
    _mock_dem(mocker, np.full((2, 2), 1.0, dtype=np.float32))
    job_session = MagicMock()

    suggestions = (
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            MagicMock(), job_session, []
        )
    )

    assert suggestions == []
    job_session.add_all.assert_called_once_with([])


def test_nothing_is_inserted_when_a_mask_cannot_be_checked(mocker: MockerFixture):
    _mock_sources(
        mocker,
        _source_frame([_LAKE, _FAR_AWAY_LAKE], ["sea_part", "sea_part"]),
    )
    postgis_reader = mocker.patch("pinta_processing.reader.PostgisReader")
    postgis_reader.return_value.process.side_effect = [
        core.RasterDataset(
            array=np.array([[1.0, 1.5]], dtype=np.float32),
            transform=constants.DEFAULT_TRANSFORM,
            crs=constants.DEFAULT_CRS,
            nodata=constants.DEFAULT_NODATA,
        ),
        ValueError("No raster data found in dem.dem for the given clipping geometry"),
    ]
    job_session = MagicMock()

    with pytest.raises(ValueError, match="No raster data found"):
        masked_update_area_suggestions.insert_update_area_suggestions_with_elevation(
            MagicMock(), job_session, []
        )

    # The first mask was uneven, but rest of batch is committed.
    job_session.add_all.assert_called_once()
    assert _LAKE.wkt in job_session.add_all.mock_calls[0][1][0][0].geom
