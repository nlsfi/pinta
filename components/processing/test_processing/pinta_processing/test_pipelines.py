# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path
from unittest.mock import MagicMock

from pinta_db.job_db.models import user
from pinta_db_utils.postgis import raster
from pytest_mock import MockerFixture
from shapely import wkt as shapely_wkt

from pinta_processing import filters, pipelines
from pinta_processing.writer import WriterMode


def test_las2dem_to_postgis_uses_extra_param_defaults(mocker: MockerFixture) -> None:

    las2dem_reader = mocker.patch(
        "pinta_processing.reader.Las2DemReader",
        return_value=MagicMock(),
    )

    pipelines.las2dem_to_postgis(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        input_path=Path("/tmp/dir/N5122B4_1.laz"),
        step=1,
        keep_class=[2],
    )

    assert las2dem_reader.call_args.kwargs["extra_lastools_params"] == {
        "buffered": 300,
        "kill": 300,
        "ncols": 500,
        "nrows": 500,
        "ll": [503000, 6903000],
    }


def test_las2dem_to_postgis_override_extra_param_defaults(
    mocker: MockerFixture,
) -> None:

    las2dem_reader = mocker.patch(
        "pinta_processing.reader.Las2DemReader",
        return_value=MagicMock(),
    )

    pipelines.las2dem_to_postgis(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        input_path=Path("/tmp/dir/N5122B4_1.laz"),
        step=1,
        keep_class=[2],
        extra_lastools_params={
            "buffered": 100,
            "ncols": 200,
            "neighbors": ["a.laz", "b.laz", "c.laz"],
            "ll": [111, 222],
        },
    )

    assert las2dem_reader.call_args.kwargs["extra_lastools_params"] == {
        "buffered": 100,
        "kill": 300,
        "ncols": 200,
        "nrows": 500,
        "ll": [111, 222],
        "neighbors": ["a.laz", "b.laz", "c.laz"],
    }


def test_dissolve_update_area_unions_and_interpolates_donut(
    mocker: MockerFixture,
) -> None:
    postgis_reader = mocker.patch(
        "pinta_processing.reader.PostgisReader",
        return_value=MagicMock(),
    )
    union = mocker.patch(
        "pinta_processing.filters.RasterUnion",
        return_value=MagicMock(),
    )
    interpolate = mocker.patch(
        "pinta_processing.filters.RasterInterpolate",
        return_value=MagicMock(),
    )
    downsample = mocker.patch(
        "pinta_processing.filters.DownsampleOverview",
        return_value=MagicMock(),
    )
    postgis_writer = mocker.patch(
        "pinta_processing.writer.RasterPostgisWriter",
        return_value=MagicMock(),
    )
    primary_session = MagicMock()
    job_session = MagicMock()
    geom_wkt = "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))"
    geom = shapely_wkt.loads(geom_wkt)

    pipelines.dissolve_update_area(
        primary_session=primary_session,
        job_session=job_session,
        update_area=user.UpdateArea(geom=geom_wkt),
    )

    # Two readers: primary DEM (seam read buffer) and reference DEM (update
    # area), identified by session since construction order does not matter.
    assert postgis_reader.call_count == 2
    calls_by_session = {call.args[2]: call for call in postgis_reader.call_args_list}
    primary_call = calls_by_session[primary_session]
    reference_call = calls_by_session[job_session]

    primary_wkt = shapely_wkt.loads(primary_call.args[3])
    reference_wkt = shapely_wkt.loads(reference_call.args[3])
    _assert_geometries_match(
        primary_wkt,
        geom.buffer(pipelines.DISSOLVE_PRIMARY_DEM_BUFFER).difference(geom),
    )
    # The primary DEM read is a ring: the update area interior is clipped out
    # because the reference DEM wins there in the union anyway.
    assert len(primary_wkt.interiors) == 1
    _assert_geometries_match(reference_wkt, geom)

    # The two DEMs are unioned before the seam is interpolated.
    union.assert_called_once_with()

    # The interpolate stage receives the donut ring between 4 m buffer and geom.
    donut = shapely_wkt.loads(interpolate.call_args.args[0])
    _assert_geometries_match(
        donut, geom.buffer(pipelines.DISSOLVE_INTERPOLATE_AREA_BUFFER).difference(geom)
    )
    # The donut has a hole (the update area) cut out of it.
    assert len(donut.interiors) == 1

    # The blended patch is merged into dem_preview and its overviews: one base
    # writer plus one writer per overview level, all in update mode.
    levels = raster.DEFAULT_OVERVIEW_LEVELS
    assert downsample.call_count == len(levels)
    assert postgis_writer.call_count == 1 + len(levels)
    assert all(
        call.kwargs["mode"] is WriterMode.UPDATE
        for call in postgis_writer.call_args_list
    )


def test_dissolve_update_area_with_holes_builds_multipart_seam_zone(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "pinta_processing.reader.PostgisReader",
        return_value=MagicMock(),
    )
    mocker.patch(
        "pinta_processing.filters.DownsampleOverview",
        return_value=MagicMock(),
    )
    mocker.patch(
        "pinta_processing.writer.RasterPostgisWriter",
        return_value=MagicMock(),
    )
    # The real filter is constructed here, its WKT validation is the regression.
    interpolate = mocker.patch(
        "pinta_processing.filters.RasterInterpolate",
        wraps=filters.RasterInterpolate,
    )
    # A lake with an island: the seam zone is the outer donut plus a ring
    # inside the island.
    geom_wkt = (
        "POLYGON ((0 0, 0 100, 100 100, 100 0, 0 0), "
        "(40 40, 40 60, 60 60, 60 40, 40 40))"
    )

    pipelines.dissolve_update_area(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        update_area=user.UpdateArea(geom=geom_wkt),
    )

    seam_zone = shapely_wkt.loads(interpolate.call_args.args[0])
    assert seam_zone.geom_type == "MultiPolygon"
    assert len(seam_zone.geoms) == 2


def test_dissolve_update_area_with_elevation_masks_instead_of_reading_reference(
    mocker: MockerFixture,
) -> None:
    postgis_reader = mocker.patch(
        "pinta_processing.reader.PostgisReader",
        return_value=MagicMock(),
    )
    mask = mocker.patch(
        "pinta_processing.filters.RasterMask",
        return_value=MagicMock(),
    )
    union = mocker.patch(
        "pinta_processing.filters.RasterUnion",
        return_value=MagicMock(),
    )
    mocker.patch(
        "pinta_processing.filters.RasterInterpolate",
        return_value=MagicMock(),
    )
    mocker.patch(
        "pinta_processing.filters.DownsampleOverview",
        return_value=MagicMock(),
    )
    mocker.patch(
        "pinta_processing.writer.RasterPostgisWriter",
        return_value=MagicMock(),
    )
    geom_wkt = "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))"
    geom = shapely_wkt.loads(geom_wkt)

    pipelines.dissolve_update_area(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        update_area=user.UpdateArea(geom=geom_wkt, elevation=123.5),
    )

    # The reference DEM is never read: the only reader is the primary DEM ring.
    postgis_reader.assert_called_once()
    primary_wkt = shapely_wkt.loads(postgis_reader.call_args.args[3])
    _assert_geometries_match(
        primary_wkt,
        geom.buffer(pipelines.DISSOLVE_PRIMARY_DEM_BUFFER).difference(geom),
    )

    # A flat raster at the update area elevation replaces the reference DEM read
    # and is still unioned with the primary DEM.
    mask.assert_called_once()
    mask_wkt, mask_elevation = mask.call_args.args
    _assert_geometries_match(shapely_wkt.loads(mask_wkt), geom)
    assert mask_elevation == 123.5
    union.assert_called_once_with()


def test_postgis_to_postgis_update_mode_propagates_to_writers(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "pinta_processing.reader.PostgisReader",
        return_value=MagicMock(),
    )
    postgis_writer = mocker.patch(
        "pinta_processing.writer.RasterPostgisWriter",
        return_value=MagicMock(),
    )

    pipelines.postgis_to_postgis(
        from_session=MagicMock(),
        from_schema="user_data",
        from_table="dem_preview",
        to_session=MagicMock(),
        to_schema="dem",
        to_table="dem",
        tile_wkt="POINT (0 0)",
        staging_tables=0,
        mode=WriterMode.UPDATE,
    )

    # The base writer and every overview writer merge into existing tiles.
    levels = raster.DEFAULT_OVERVIEW_LEVELS
    assert postgis_writer.call_count == 1 + len(levels)
    assert all(
        call.kwargs["mode"] is WriterMode.UPDATE
        for call in postgis_writer.call_args_list
    )


def test_postgis_to_postgis(
    mocker: MockerFixture,
) -> None:
    postgis_reader = mocker.patch(
        "pinta_processing.reader.PostgisReader",
        return_value=MagicMock(),
    )
    postgis_writer = mocker.patch(
        "pinta_processing.writer.RasterPostgisWriter",
        return_value=MagicMock(),
    )
    from_session = MagicMock()
    to_session = MagicMock()

    pipelines.postgis_to_postgis(
        from_session=from_session,
        from_schema="dem",
        from_table="dem",
        to_session=to_session,
        to_schema="user_data",
        to_table="dem_preview",
        tile_wkt="POINT (0 0)",
        staging_tables=2,
    )

    # Reads the source table with the source session and tile geometry.
    postgis_reader.assert_called_once_with("dem", "dem", from_session, "POINT (0 0)")

    # The final writer targets the destination table/session with staging tables.
    # (Overview writers also use RasterPostgisWriter, so assert on the last call.)
    assert (
        mocker.call("user_data", "dem_preview", to_session, 2, mode=WriterMode.INSERT)
        in postgis_writer.call_args_list
    )


def _assert_geometries_match(actual: object, expected: object) -> None:
    # WKT round-tripping perturbs vertices slightly, so compare with tolerance.
    assert actual.symmetric_difference(expected).area < 1e-6  # type: ignore[attr-defined]
