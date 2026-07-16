# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag, dagbag

from pinta_dags.dags import dissolve_update_areas

if TYPE_CHECKING:
    from collections.abc import Callable

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = dissolve_update_areas.create_dissolve_update_areas_dag(
        dag_id=f"some_id_{uuid.uuid4()}"
    )

    assert str(dag.dag_id).startswith("some_id")

    dag_bag = DagBag(include_examples=False)
    dag_bag.bag_dag(dag)
    dagbag.sync_bag_to_db(dag_bag, "mock-dags", None)

    return dag


@pytest.fixture(autouse=True)
def mock_airflow_settings(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_PROCESSING_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB_ADMIN", "postgres://mockaddr:123/db")
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB", "postgres://mockaddr:123/db")
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES", "2"
    )


def test_dissolve_update_areas_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "set_processing_status_started",
        "get_database_name",
        "build_job_connection_uri_task",
        "find_dirty_update_areas",
        "ensure_dem_preview_coverage",
        "dissolve_update_area",
        "set_processing_status_completed",
        "set_processing_status_failed",
    }


def test_dependencies() -> None:
    dag = create_dag_to_test()
    assert dag is not None

    status_started = dag.get_task("set_processing_status_started")
    get_database_name = dag.get_task("get_database_name")
    build_job_connection_uri_task = dag.get_task("build_job_connection_uri_task")
    find_dirty_update_areas = dag.get_task("find_dirty_update_areas")
    ensure_dem_preview_coverage = dag.get_task("ensure_dem_preview_coverage")
    dissolve_update_area = dag.get_task("dissolve_update_area")

    assert status_started.task_id in get_database_name.upstream_task_ids
    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    assert (
        build_job_connection_uri_task.task_id
        in find_dirty_update_areas.upstream_task_ids
    )
    # Missing preview tiles are copied in before any area is dissolved.
    assert (
        find_dirty_update_areas.task_id in ensure_dem_preview_coverage.upstream_task_ids
    )
    assert ensure_dem_preview_coverage.task_id in dissolve_update_area.upstream_task_ids


def test_processing_status_tasks() -> None:
    dag = create_dag_to_test()

    status_completed = dag.get_task("set_processing_status_completed")
    status_failed = dag.get_task("set_processing_status_failed")

    # Both terminal status tasks fan in from every step that can fail so the
    # status is always resolved, even when an early step fails.
    expected_upstream = {
        "set_processing_status_started",
        "get_database_name",
        "build_job_connection_uri_task",
        "find_dirty_update_areas",
        "ensure_dem_preview_coverage",
        "dissolve_update_area",
    }
    assert expected_upstream <= status_completed.upstream_task_ids
    assert expected_upstream <= status_failed.upstream_task_ids

    assert status_completed.trigger_rule == "none_failed"
    assert status_failed.trigger_rule == "one_failed"


def test_get_max_parallel_pipelines_reads_variable() -> None:
    assert dissolve_update_areas._get_max_parallel_pipelines() == 2


def test_get_max_parallel_pipelines_rejects_below_one(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES", "0"
    )
    with pytest.raises(ValueError, match="must be at least 1"):
        dissolve_update_areas._get_max_parallel_pipelines()


def test_get_max_parallel_pipelines_defaults_when_unset(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.delenv(
        "AIRFLOW_VAR_PINTA_DISSOLVE_UPDATE_AREAS_MAX_PARALLEL_PIPELINES",
        raising=False,
    )
    assert dissolve_update_areas._get_max_parallel_pipelines() == 4


def test_dissolve_update_area_builds_and_executes_pipeline(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocker.patch("sqlalchemy.create_engine")
    session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.return_value = session

    update_area = MagicMock(dirty=True)
    session.exec.return_value.first.return_value = update_area

    # Inject a mock pipelines module so the task body's ``from pinta_processing
    # import pipelines`` resolves to the mock instead of importing the real
    # (heavy) module.
    mock_pipeline = MagicMock()
    mock_pipelines_module = mock_submodule("pinta_processing.pipelines")
    mock_pipelines_module.dissolve_update_area.return_value = mock_pipeline

    dag = create_dag_to_test()
    dissolve_update_area = dag.get_task("dissolve_update_area").python_callable

    dissolve_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
    )

    mock_pipelines_module.dissolve_update_area.assert_called_once()
    kwargs = mock_pipelines_module.dissolve_update_area.call_args.kwargs
    # The pipeline receives the fetched update area model instance itself.
    assert kwargs["update_area"] is update_area
    assert "primary_session" in kwargs
    assert "job_session" in kwargs
    mock_pipeline.execute.assert_called_once_with()


def _run_ensure_dem_preview_coverage(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
    *,
    preview_tile_complete: bool,
    preview_tile_exists: bool,
    primary_tile_exists: bool,
    update_area_deleted: bool = False,
) -> dict[str, MagicMock]:
    """Run the ensure task body with mocked sessions and processing modules."""
    mocker.patch("sqlalchemy.create_engine")
    primary_session = MagicMock()
    job_session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    # The task opens the primary session first, then the job session.
    session_ctx.return_value.__enter__.side_effect = [primary_session, job_session]

    update_area = None
    if not update_area_deleted:
        update_area = MagicMock(geom_wkt="POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))")
    job_session.exec.return_value.first.return_value = update_area

    mock_pipelines = mock_submodule("pinta_processing.pipelines")
    mock_pipelines.DISSOLVE_PRIMARY_DEM_BUFFER = 24.0
    mock_reader = mock_submodule("pinta_processing.reader")
    mock_writer = mock_submodule("pinta_processing.writer")
    mock_tiles = mock_submodule("pinta_processing.utils.tiles")
    envelope = MagicMock(wkt="ENVELOPE WKT")
    mock_tiles.tile_envelopes.return_value = [envelope]

    def tile_exists(session: MagicMock, *_args: object, mode: object = None) -> bool:
        if mode is not None:
            # The completeness probe passes mode=ALL_PIXELS_HAVE_DATA.
            return preview_tile_complete
        return preview_tile_exists if session is job_session else primary_tile_exists

    mock_tiles.tile_exists.side_effect = tile_exists

    dag = create_dag_to_test()
    ensure_coverage = dag.get_task("ensure_dem_preview_coverage").python_callable
    ensure_coverage(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
    )

    return {
        "primary_session": primary_session,
        "job_session": job_session,
        "reader": mock_reader,
        "writer": mock_writer,
        "tiles": mock_tiles,
        "envelope": envelope,
    }


def test_ensure_dem_preview_coverage_inserts_missing_tiles_per_level(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocks = _run_ensure_dem_preview_coverage(
        mocker,
        mock_submodule,
        preview_tile_complete=False,
        preview_tile_exists=False,
        primary_tile_exists=True,
    )
    postgis_reader = mocks["reader"].PostgisReader
    postgis_writer = mocks["writer"].RasterPostgisWriter

    # One pg-to-pg copy per resolution: the base DEM and each overview
    # level, read from the primary table and written to the preview table.
    assert [call.args[1] for call in postgis_reader.call_args_list] == [
        "dem",
        "o_2_dem",
        "o_8_dem",
        "o_128_dem",
    ]
    assert all(
        call.args[0] == "dem"
        and call.args[2] is mocks["primary_session"]
        and call.args[3] == mocks["envelope"].wkt
        for call in postgis_reader.call_args_list
    )
    assert [call.args[1] for call in postgis_writer.call_args_list] == [
        "dem_preview",
        "o_2_dem_preview",
        "o_8_dem_preview",
        "o_128_dem_preview",
    ]
    # A tile with no preview row at all is inserted as a brand new row.
    assert all(
        call.args[2] is mocks["job_session"]
        and call.kwargs["mode"] is mocks["writer"].WriterMode.INSERT
        for call in postgis_writer.call_args_list
    )
    assert postgis_reader.return_value.__or__.return_value.execute.call_count == 4

    # The tile grid is enumerated at the level-scaled pixel size.
    pixel_sizes = [
        call.kwargs["pixel_size"]
        for call in mocks["tiles"].tile_envelopes.call_args_list
    ]
    base = pixel_sizes[0]
    assert pixel_sizes == [base, base * 2, base * 8, base * 128]


def test_ensure_dem_preview_coverage_updates_partial_tiles(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocks = _run_ensure_dem_preview_coverage(
        mocker,
        mock_submodule,
        preview_tile_complete=False,
        preview_tile_exists=True,
        primary_tile_exists=True,
    )
    postgis_writer = mocks["writer"].RasterPostgisWriter

    # A tile that exists but carries nodata (production area boundary) is
    # refreshed from the primary DEM by merging into the existing row.
    assert postgis_writer.call_count == 4
    assert all(
        call.kwargs["mode"] is mocks["writer"].WriterMode.UPDATE
        for call in postgis_writer.call_args_list
    )


def test_ensure_dem_preview_coverage_skips_complete_tiles(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocks = _run_ensure_dem_preview_coverage(
        mocker,
        mock_submodule,
        preview_tile_complete=True,
        preview_tile_exists=True,
        primary_tile_exists=True,
    )

    # The preview fully covers the footprint at every level: nothing to copy.
    mocks["reader"].PostgisReader.assert_not_called()
    mocks["writer"].RasterPostgisWriter.assert_not_called()


@pytest.mark.parametrize("preview_tile_exists", [False, True])
def test_ensure_dem_preview_coverage_fails_without_primary_tile(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
    preview_tile_exists: bool,
) -> None:
    # The preview can only ever be filled from the primary DEM: a tile that is
    # not fully covered in the preview (partial or missing entirely) and has
    # no primary DEM tile under it means the update area extends beyond the
    # DEM coverage and cannot be processed.
    with pytest.raises(ValueError, match="beyond the DEM coverage"):
        _run_ensure_dem_preview_coverage(
            mocker,
            mock_submodule,
            preview_tile_complete=False,
            preview_tile_exists=preview_tile_exists,
            primary_tile_exists=False,
        )


def test_ensure_dem_preview_coverage_skips_deleted_area(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocks = _run_ensure_dem_preview_coverage(
        mocker,
        mock_submodule,
        preview_tile_complete=False,
        preview_tile_exists=False,
        primary_tile_exists=True,
        update_area_deleted=True,
    )

    # An area deleted after it was listed has no tiles to copy.
    mocks["tiles"].tile_envelopes.assert_not_called()
    mocks["reader"].PostgisReader.assert_not_called()


def test_dissolve_update_area_clears_dirty_flag(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocker.patch("sqlalchemy.create_engine")
    session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.return_value = session

    update_area = MagicMock(dirty=True)
    session.exec.return_value.first.return_value = update_area

    mock_submodule("pinta_processing.pipelines")

    dag = create_dag_to_test()
    dissolve_update_area = dag.get_task("dissolve_update_area").python_callable

    dissolve_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
    )

    # After a successful dissolve the worker marks the area clean and commits it.
    assert update_area.dirty is False
    session.add.assert_called_once_with(update_area)
    session.commit.assert_called_once_with()


def test_dissolve_update_area_skips_deleted_area(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocker.patch("sqlalchemy.create_engine")
    session = MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.return_value = session

    session.exec.return_value.first.return_value = None

    mock_pipelines_module = mock_submodule("pinta_processing.pipelines")

    dag = create_dag_to_test()
    dissolve_update_area = dag.get_task("dissolve_update_area").python_callable

    dissolve_update_area(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        update_area_id="00000000-0000-0000-0000-000000000000",
    )

    # An area deleted after it was listed dissolves nothing and commits nothing.
    mock_pipelines_module.dissolve_update_area.assert_not_called()
    session.commit.assert_not_called()
