# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pinta_dags import tasks

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def mock_session(mocker: "MockerFixture") -> MagicMock:
    """Patch the engine/session so task bodies run without a real database."""
    mocker.patch("sqlalchemy.create_engine")
    session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.return_value = session
    return session


def test_get_database_name_returns_database_name(mock_session: MagicMock) -> None:
    area = MagicMock(database_name="job_db")
    mock_session.exec.return_value.first.return_value = area

    result = tasks.get_database_name.function(
        "postgres://mock/db", "some-production-area-id"
    )

    assert result == "job_db"


@pytest.mark.parametrize("area", [None, MagicMock(database_name=None)])
def test_get_database_name_raises_without_database_name(
    mock_session: MagicMock, area: object
) -> None:
    mock_session.exec.return_value.first.return_value = area

    with pytest.raises(ValueError, match="no database name set"):
        tasks.get_database_name.function("postgres://mock/db", "prod-area-id")


def test_find_production_area_tile_paths_returns_file_paths(
    mock_session: MagicMock,
) -> None:
    area = MagicMock(
        tiles=[MagicMock(file_path="/a.laz"), MagicMock(file_path="/b.laz")]
    )
    mock_session.exec.return_value.first.return_value = area

    result = tasks.find_production_area_tile_paths.function(
        "postgres://mock/db", "prod-area-id"
    )

    assert result == ["/a.laz", "/b.laz"]


def test_find_production_area_tile_paths_missing_area_returns_empty(
    mock_session: MagicMock,
) -> None:
    mock_session.exec.return_value.first.return_value = None

    result = tasks.find_production_area_tile_paths.function(
        "postgres://mock/db", "prod-area-id"
    )

    assert result == []


def test_find_production_area_tile_geometries_returns_wkt(
    mock_session: MagicMock, mocker: "MockerFixture"
) -> None:
    mocker.patch(
        "geoalchemy2.shape.to_shape",
        side_effect=[MagicMock(wkt="POINT (0 0)"), MagicMock(wkt="POINT (1 1)")],
    )
    area = MagicMock(tiles=[MagicMock(), MagicMock()])
    mock_session.exec.return_value.first.return_value = area

    result = tasks.find_production_area_tile_geometries.function(
        "postgres://mock/db", "prod-area-id"
    )

    assert result == ["POINT (0 0)", "POINT (1 1)"]


def test_find_production_area_tile_geometries_missing_area_returns_empty(
    mock_session: MagicMock,
) -> None:
    mock_session.exec.return_value.first.return_value = None

    result = tasks.find_production_area_tile_geometries.function(
        "postgres://mock/db", "prod-area-id"
    )

    assert result == []


def test_find_dirty_update_areas_returns_id_and_geom(
    mock_session: MagicMock, mocker: "MockerFixture"
) -> None:
    mocker.patch(
        "geoalchemy2.shape.to_shape",
        side_effect=[MagicMock(wkt="POLYGON ((0 0, 0 1, 1 1, 0 0))")],
    )
    area = MagicMock(geom=MagicMock())
    area.id = "area-1"
    mock_session.exec.return_value.all.return_value = [area]

    result = tasks.find_dirty_update_areas.function("postgres://mock/db")

    assert result == [
        {"update_area_id": "area-1", "geom_wkt": "POLYGON ((0 0, 0 1, 1 1, 0 0))"}
    ]


def test_find_dirty_update_areas_filters_on_dirty(mock_session: MagicMock) -> None:
    mock_session.exec.return_value.all.return_value = []

    tasks.find_dirty_update_areas.function("postgres://mock/db")

    # The query must only select dirty rows so clean areas are never re-dissolved.
    statement = mock_session.exec.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "dirty" in compiled.lower()
    assert "is true" in compiled.lower()


def test_find_dirty_update_areas_no_dirty_areas_returns_empty(
    mock_session: MagicMock,
) -> None:
    mock_session.exec.return_value.all.return_value = []

    result = tasks.find_dirty_update_areas.function("postgres://mock/db")

    assert result == []


def test_build_job_connection_uri_task_replaces_database_name() -> None:
    result = tasks.build_job_connection_uri_task.function(
        base_uri="postgresql://user:pass@host:1234/template_db",
        database_name="job_test",
    )

    assert result == "postgresql://user:pass@host:1234/job_test"
