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


def test_find_dirty_update_areas_returns_ids(mock_session: MagicMock) -> None:
    area = MagicMock()
    area.id = "area-1"
    mock_session.exec.return_value.all.return_value = [area]

    result = tasks.find_dirty_update_areas.function("postgres://mock/db")

    assert result == [{"update_area_id": "area-1"}]


def test_find_dirty_update_areas_filters_on_dirty(mock_session: MagicMock) -> None:
    mock_session.exec.return_value.all.return_value = []

    tasks.find_dirty_update_areas.function("postgres://mock/db")

    # The query must only select dirty rows so clean areas are never re-dissolved.
    statement = mock_session.exec.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "dirty" in compiled.lower()
    assert "is true" in compiled.lower()


def test_find_dirty_update_areas_excludes_registered(mock_session: MagicMock) -> None:
    mock_session.exec.return_value.all.return_value = []

    tasks.find_dirty_update_areas.function("postgres://mock/db")

    # A registered area is frozen, so it must never be picked up again.
    statement = mock_session.exec.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "registered_at is null" in compiled.lower()


def test_find_dirty_update_areas_no_dirty_areas_returns_empty(
    mock_session: MagicMock,
) -> None:
    mock_session.exec.return_value.all.return_value = []

    result = tasks.find_dirty_update_areas.function("postgres://mock/db")

    assert result == []


def test_find_unregistered_update_areas_returns_ids_and_wkt(
    mock_session: MagicMock, mocker: "MockerFixture"
) -> None:
    mocker.patch(
        "geoalchemy2.shape.to_shape",
        side_effect=[MagicMock(wkt="POINT (0 0)"), MagicMock(wkt="POINT (1 1)")],
    )
    area_1 = MagicMock()
    area_1.id = "area-1"
    area_2 = MagicMock()
    area_2.id = "area-2"
    mock_session.exec.return_value.all.return_value = [area_1, area_2]

    result = tasks.find_unregistered_update_areas.function("postgres://mock/db")

    # Each area's id stays paired with its own geometry.
    assert result == [
        {"update_area_id": "area-1", "geom_wkt": "POINT (0 0)"},
        {"update_area_id": "area-2", "geom_wkt": "POINT (1 1)"},
    ]


def test_find_unregistered_update_areas_excludes_registered(
    mock_session: MagicMock,
) -> None:
    mock_session.exec.return_value.all.return_value = []

    result = tasks.find_unregistered_update_areas.function("postgres://mock/db")

    assert result == []
    statement = mock_session.exec.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "registered_at is null" in compiled.lower()


def test_restore_update_area_write_access_grants_by_default(
    mock_session: MagicMock, mocker: "MockerFixture"
) -> None:
    restore = mocker.patch(
        "pinta_db.job_db.privileges.restore_update_area_write_access"
    )

    tasks.restore_update_area_write_access.function("postgres://mock/db")

    restore.assert_called_once()


def test_restore_update_area_write_access_skipped_when_disabled(
    mocker: "MockerFixture",
) -> None:
    create_engine = mocker.patch("sqlalchemy.create_engine")

    tasks.restore_update_area_write_access.function("postgres://mock/db", enabled=False)

    create_engine.assert_not_called()


def test_find_restore_areas_returns_id_and_geom_wkt(
    mock_session: MagicMock, mocker: "MockerFixture"
) -> None:
    row_1 = MagicMock(id="restore-1", geom="geom-1")
    row_2 = MagicMock(id="restore-2", geom="geom-2")
    mock_session.exec.return_value.all.return_value = [row_1, row_2]

    mocker.patch(
        "geoalchemy2.shape.to_shape",
        side_effect=[
            MagicMock(wkt="POLYGON ((0 0, 0 1, 1 1, 0 0))"),
            MagicMock(wkt="POLYGON ((1 1, 1 2, 2 2, 1 1))"),
        ],
    )

    result = tasks.find_restore_areas.function("postgres://mock/db")

    assert result == [
        {"restore_id": "restore-1", "geom_wkt": "POLYGON ((0 0, 0 1, 1 1, 0 0))"},
        {"restore_id": "restore-2", "geom_wkt": "POLYGON ((1 1, 1 2, 2 2, 1 1))"},
    ]


def test_delete_restore_area_deletes_existing_row(mock_session: MagicMock) -> None:
    restore_row = MagicMock()
    mock_session.get.return_value = restore_row

    tasks.delete_restore_area.function("postgres://mock/db", "restore-1")

    mock_session.get.assert_called_once()
    mock_session.delete.assert_called_once_with(restore_row)
    mock_session.commit.assert_called_once_with()


def test_delete_restore_area_is_idempotent_when_missing(
    mock_session: MagicMock,
) -> None:
    mock_session.get.return_value = None

    tasks.delete_restore_area.function("postgres://mock/db", "restore-1")

    mock_session.get.assert_called_once()
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()


def test_build_job_connection_uri_task_replaces_database_name() -> None:
    result = tasks.build_job_connection_uri_task.function(
        base_uri="postgresql://user:pass@host:1234/template_db",
        database_name="job_test",
    )

    assert result == "postgresql://user:pass@host:1234/job_test"
