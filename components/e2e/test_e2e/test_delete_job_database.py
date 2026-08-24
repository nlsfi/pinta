# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
import uuid

import pytest
import requests
import sqlmodel
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pinta_db_test_utils import db_utils
from pinta_db_utils import database_utils, engine_utils
from pinta_e2e_utils import layers

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot
    from sqlmodel import Session

# Dropping a database is a single statement, but the request still travels
# through the containerized backend.
DELETE_TIMEOUT_MS = 30000

PRODUCTION_AREA_WKT = "MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))"


def _get_production_area(db: "Session") -> ProductionArea:
    db.expire_all()
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    return production_area


def _job_database_exists(database_name: str) -> bool:
    """Return whether the job database is still present in the cluster."""
    credentials = db_utils.get_job_admin_credentials("postgres")
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return (
            connection.execute(
                sqlmodel.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            ).first()
            is not None
        )


def _create_production_area(db: "Session", status: ProcessingStatus) -> ProductionArea:
    """Insert a production area and move it to ``status`` in a second statement.

    The status is changed after the insert so the primary db's
    ``update_processing_timestamp`` trigger stamps
    ``processing_status_last_updated``, the way a real processing run does.
    """
    production_area = ProductionArea(name="Area 1", geom=PRODUCTION_AREA_WKT)
    db.add(production_area)
    db.commit()

    production_area.processing_status = status
    db.add(production_area)
    db.commit()
    assert production_area.processing_status_last_updated is not None
    return production_area


@pytest.fixture
def production_area_with_job_database(
    db: "Session",
    _provisioned_job_dbs: set[str],
) -> ProductionArea:
    """Insert a processed production area and clone its job database.

    The orchestrator DAG normally provisions the job db and stamps
    ``database_name``; do the same by hand so the test does not depend on a
    full processing run.
    """
    production_area = _create_production_area(db, ProcessingStatus.COMPLETED)

    database_name = f"job_{production_area.id}"
    # Registered for the session teardown in case this test leaves it behind.
    _provisioned_job_dbs.add(database_name)
    production_area.database_name = database_name
    db.add(production_area)
    db.commit()

    with engine_utils.get_autocommit_connection(
        db_utils.get_job_admin_credentials("postgres")
    ) as admin_connection:
        database_utils.initialize_db_from_template(
            admin_connection, database_name, replace_existing=True
        )
    assert _job_database_exists(database_name)
    return production_area


def test_delete_job_database_action_drops_database_and_resets_production_area(
    production_area_with_job_database: ProductionArea,
    qgis_plugin: "Plugin",
    qtbot: "QtBot",
    m_error_dialog: "MagicMock",
    mocker: "MockerFixture",
    db: "Session",
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )
    from pinta_qgis_plugin.project.groups.job_layer_collection import (  # noqa: PLC0415
        JobLayerCollection,
    )
    from pinta_qgis_plugin.utils import messages  # noqa: PLC0415

    production_area_id = str(production_area_with_job_database.id)
    database_name = production_area_with_job_database.database_name
    assert database_name is not None

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    production_area_layer.reload()
    assert production_area_layer.featureCount() == 1
    feature = next(production_area_layer.getFeatures())

    # Open the job layers first: they read the database that is about to go.
    open_action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_OPEN_PRODUCTION_AREA_LAYERS,
    )
    layers.run_layer_action(production_area_layer, open_action, feature)
    assert JobLayerCollection.get().find_layers()

    mock_ask_confirmation = mocker.patch.object(
        messages, "ask_confirmation", return_value=True
    )
    delete_action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_DELETE_JOB_DATABASE,
    )

    client = api_client.get_api_client()
    with qtbot.waitSignal(
        client.job_database_deleted, timeout=DELETE_TIMEOUT_MS
    ) as blocker:
        layers.run_layer_action(production_area_layer, delete_action, feature)

    assert blocker.args == [production_area_id]
    mock_ask_confirmation.assert_called_once()
    m_error_dialog.assert_not_called()

    assert not _job_database_exists(database_name)

    updated = _get_production_area(db)
    assert updated.database_name is None
    assert updated.processing_status == ProcessingStatus.NOT_STARTED
    assert updated.processing_status_last_updated is not None

    # The layers reading the deleted database are closed with it.
    assert not JobLayerCollection.get().find_layers()


def test_delete_job_database_action_is_cancelled_without_confirmation(
    production_area_with_job_database: ProductionArea,
    qgis_plugin: "Plugin",
    m_error_dialog: "MagicMock",
    mocker: "MockerFixture",
    db: "Session",
) -> None:
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )
    from pinta_qgis_plugin.utils import messages  # noqa: PLC0415

    database_name = production_area_with_job_database.database_name
    assert database_name is not None

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    production_area_layer.reload()
    feature = next(production_area_layer.getFeatures())

    mocker.patch.object(messages, "ask_confirmation", return_value=False)
    delete_action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_DELETE_JOB_DATABASE,
    )

    layers.run_layer_action(production_area_layer, delete_action, feature)

    m_error_dialog.assert_not_called()
    assert _job_database_exists(database_name)

    unchanged = _get_production_area(db)
    assert unchanged.database_name == database_name
    assert unchanged.processing_status == ProcessingStatus.COMPLETED


def test_delete_job_database_resets_production_area_without_a_database(
    db: "Session",
    backend_url: str,
    backend_db_override_headers: dict[str, str],
) -> None:
    production_area = _create_production_area(db, ProcessingStatus.FAILURE)

    response = requests.delete(
        f"{backend_url}/production-areas/{production_area.id}/database",
        headers={"Accept-Language": "en", **backend_db_override_headers},
        timeout=30,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["production_area_id"] == str(production_area.id)
    assert body["database_name"] is None

    updated = _get_production_area(db)
    assert updated.processing_status == ProcessingStatus.NOT_STARTED
    assert updated.processing_status_last_updated is not None


def test_delete_job_database_is_refused_while_a_run_is_in_flight(
    production_area_with_job_database: ProductionArea,
    db: "Session",
    backend_url: str,
    backend_db_override_headers: dict[str, str],
) -> None:
    """A STARTED run still owns the database, so the drop must be refused."""
    database_name = production_area_with_job_database.database_name
    assert database_name is not None
    production_area_with_job_database.processing_status = ProcessingStatus.STARTED
    db.add(production_area_with_job_database)
    db.commit()

    response = requests.delete(
        f"{backend_url}/production-areas/{production_area_with_job_database.id}"
        "/database",
        headers={"Accept-Language": "en", **backend_db_override_headers},
        timeout=30,
    )

    assert response.status_code == 400, response.text
    assert "started" in response.json()["detail"]
    assert _job_database_exists(database_name)

    unchanged = _get_production_area(db)
    assert unchanged.database_name == database_name
    assert unchanged.processing_status == ProcessingStatus.STARTED


def test_delete_job_database_refuses_a_database_outside_the_job_namespace(
    db: "Session",
    backend_url: str,
    backend_db_override_headers: dict[str, str],
) -> None:
    """A name the DAGs would never provision must not reach DROP DATABASE."""
    production_area = _create_production_area(db, ProcessingStatus.COMPLETED)
    production_area.database_name = "postgres"
    db.add(production_area)
    db.commit()

    response = requests.delete(
        f"{backend_url}/production-areas/{production_area.id}/database",
        headers={"Accept-Language": "en", **backend_db_override_headers},
        timeout=30,
    )

    assert response.status_code == 400, response.text
    assert "postgres" in response.json()["detail"]
    assert _job_database_exists("postgres")

    unchanged = _get_production_area(db)
    assert unchanged.database_name == "postgres"
    assert unchanged.processing_status == ProcessingStatus.COMPLETED


def test_delete_job_database_returns_404_for_an_unknown_production_area(
    backend_url: str,
    backend_db_override_headers: dict[str, str],
) -> None:
    response = requests.delete(
        f"{backend_url}/production-areas/{uuid.uuid4()}/database",
        headers={"Accept-Language": "en", **backend_db_override_headers},
        timeout=30,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"].startswith("Production area")
