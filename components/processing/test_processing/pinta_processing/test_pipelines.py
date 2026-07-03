# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path
from unittest.mock import MagicMock

from pinta_db_utils.postgis import raster
from pytest_mock import MockerFixture
from shapely import wkt as shapely_wkt

from pinta_processing import pipelines


def test_blast2dem_to_postgis_uses_extra_param_defaults(mocker: MockerFixture) -> None:

    blast2dem_reader = mocker.patch(
        "pinta_processing.reader.Blast2DemReader",
        return_value=MagicMock(),
    )

    pipelines.blast2dem_to_postgis(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        input_path=Path("/tmp/dir/N5122B4_1.laz"),
        step=1,
        keep_class=[2],
    )

    assert blast2dem_reader.call_args.kwargs["extra_lastools_params"] == {
        "buffered": 300,
        "kill": 300,
        "ncols": 500,
        "nrows": 500,
        "ll": [503000, 6903000],
    }


def test_blast2dem_to_postgis_override_extra_param_defaults(
    mocker: MockerFixture,
) -> None:

    blast2dem_reader = mocker.patch(
        "pinta_processing.reader.Blast2DemReader",
        return_value=MagicMock(),
    )

    pipelines.blast2dem_to_postgis(
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

    assert blast2dem_reader.call_args.kwargs["extra_lastools_params"] == {
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
        geom_wkt=geom_wkt,
    )

    # Two readers: primary DEM (50 m buffer) and reference DEM (4 m buffer).
    assert postgis_reader.call_count == 2
    primary_call, reference_call = postgis_reader.call_args_list
    assert primary_call.args[2] is primary_session
    assert reference_call.args[2] is job_session

    primary_wkt = shapely_wkt.loads(primary_call.args[3])
    reference_wkt = shapely_wkt.loads(reference_call.args[3])
    _assert_geometries_match(
        primary_wkt, geom.buffer(pipelines.DISSOLVE_PRIMARY_DEM_BUFFER)
    )
    _assert_geometries_match(
        reference_wkt, geom.buffer(pipelines.DISSOLVE_INTERPOLATE_AREA_BUFFER)
    )

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
        call.kwargs["mode"] == "update" for call in postgis_writer.call_args_list
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
        mocker.call("user_data", "dem_preview", to_session, 2)
        in postgis_writer.call_args_list
    )


def _assert_geometries_match(actual: object, expected: object) -> None:
    # WKT round-tripping perturbs vertices slightly, so compare with tolerance.
    assert actual.symmetric_difference(expected).area < 1e-6  # type: ignore[attr-defined]
