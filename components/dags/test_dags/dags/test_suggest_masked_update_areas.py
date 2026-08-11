# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag, dagbag
from pinta_common import MASK_OGR_ENV_PREFIX

from pinta_dags.dags import suggest_masked_update_areas

_MASK_SOURCES_VARIABLE = "AIRFLOW_VAR_PINTA_PROCESSING_MASK_OGR_SOURCES"

if TYPE_CHECKING:
    from collections.abc import Callable

    from airflow.sdk import DAG
    from pytest_mock import MockerFixture


def create_dag_to_test() -> "DAG":
    dag = suggest_masked_update_areas.create_suggest_masked_update_areas_dag(
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
    monkeypatch.setenv("AIRFLOW_CONN_PINTA_JOB_DB", "postgres://mockaddr:123/db")


@pytest.fixture(autouse=True)
def _clear_mask_sources(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Keep mask sources from the developer's environment out of the tests."""
    monkeypatch.delenv(_MASK_SOURCES_VARIABLE, raising=False)


def test_all_tasks() -> None:
    dag = create_dag_to_test()

    assert set(dag.task_ids) == {
        "get_database_name",
        "build_job_connection_uri_task",
        "find_production_area_geometry",
        "insert_update_area_suggestions",
    }


def test_dependencies() -> None:
    dag = create_dag_to_test()

    get_database_name = dag.get_task("get_database_name")
    build_job_connection_uri_task = dag.get_task("build_job_connection_uri_task")
    find_production_area_geometry = dag.get_task("find_production_area_geometry")
    insert_update_area_suggestions = dag.get_task("insert_update_area_suggestions")

    assert get_database_name.task_id in build_job_connection_uri_task.upstream_task_ids
    # The masks are clipped to the production area before any DEM is read.
    assert (
        find_production_area_geometry.task_id
        in insert_update_area_suggestions.upstream_task_ids
    )
    assert (
        build_job_connection_uri_task.task_id
        in insert_update_area_suggestions.upstream_task_ids
    )


def test_mask_sources_are_forwarded_into_the_task_container(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    # The sources are configured as one Airflow Variable, the processing
    # component reads them as the prefixed environment variables.
    monkeypatch.setenv(
        _MASK_SOURCES_VARIABLE,
        '{"LAKE_PARTS": "/input/lakes.gpkg", "SEA_PARTS": "/input/sea.gpkg"}',
    )

    environment = suggest_masked_update_areas._mask_container_task_args()["environment"]

    assert environment[f"{MASK_OGR_ENV_PREFIX}LAKE_PARTS"] == "/input/lakes.gpkg"
    assert environment[f"{MASK_OGR_ENV_PREFIX}SEA_PARTS"] == "/input/sea.gpkg"
    # The environment the other container tasks get is kept as well.
    assert "DB_SRID" in environment


def test_task_container_gets_no_mask_sources_when_the_variable_is_unset() -> None:
    environment = suggest_masked_update_areas._mask_container_task_args()["environment"]

    assert not [
        variable for variable in environment if variable.startswith(MASK_OGR_ENV_PREFIX)
    ]


def test_mask_sources_rejects_a_variable_that_is_not_an_object(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setenv(_MASK_SOURCES_VARIABLE, '["/input/lakes.gpkg"]')

    with pytest.raises(TypeError, match="must be a JSON object"):
        suggest_masked_update_areas._mask_container_task_args()


def test_mask_sources_do_not_leak_into_the_shared_task_args(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    from pinta_dags import config

    monkeypatch.setenv(_MASK_SOURCES_VARIABLE, '{"LAKE_PARTS": "/input/lakes.gpkg"}')

    suggest_masked_update_areas._mask_container_task_args()

    assert (
        f"{MASK_OGR_ENV_PREFIX}LAKE_PARTS"
        not in config.PINTA_CONTAINER_TASK_ARGS["environment"]
    )


def test_insert_update_area_suggestions_calls_the_script(
    mocker: "MockerFixture",
    mock_submodule: "Callable[[str], MagicMock]",
) -> None:
    mocker.patch("sqlalchemy.create_engine")
    primary_session, job_session = MagicMock(), MagicMock()
    session_ctx = mocker.patch("sqlmodel.Session")
    session_ctx.return_value.__enter__.side_effect = [primary_session, job_session]
    processing_reader = mock_submodule("pinta_processing.reader")
    sources = ["/input/lakes.gpkg"]
    processing_reader.OgrReader.sources_from_environment.return_value = sources
    scripts = mock_submodule("pinta_processing.scripts.masked_update_area_suggestions")

    dag = create_dag_to_test()
    insert_update_area_suggestions = dag.get_task(
        "insert_update_area_suggestions"
    ).python_callable

    insert_update_area_suggestions(
        primary_connection_uri="postgres://primary",
        job_connection_uri="postgres://job",
        production_area_wkt="POLYGON ((0 0, 9 0, 9 9, 0 0))",
    )

    # The DEM is read from the primary database, the suggestions are written to
    # the job database, and the sources come from the forwarded environment.
    scripts.insert_update_area_suggestions_with_elevation.assert_called_once_with(
        primary_session,
        job_session,
        sources,
        area_of_interest="POLYGON ((0 0, 9 0, 9 9, 0 0))",
    )
