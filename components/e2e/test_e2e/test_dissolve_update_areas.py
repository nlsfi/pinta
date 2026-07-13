# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

import pytest
import sqlmodel
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pinta_db_test_utils import db_utils
from pinta_db_utils import database_utils, engine_utils
from pinta_e2e_utils import layers
from pinta_e2e_utils.airflow_client import AirflowClient, DagRun

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytestqt.qtbot import QtBot
    from sqlmodel import Session

# The dissolve workflow only spins up a couple of short-lived task containers,
# but the docker pulls / cold starts can still be slow, so keep a generous budget.
WORKFLOW_TIMEOUT_S = 240.0

# Constant value the seeded reference DEM is flattened to. Chosen well outside the
# real DEM elevation range so a mean over the update area unambiguously tells the
# original DEM apart from a preview that has taken the reference values.
REFERENCE_DEM_VALUE = 1000.0

# Radius (m) of the update area probe polygon around the DEM centroid. Kept small
# so the primary DEM read (buffered 50 m) stays inside the seeded coverage.
UPDATE_AREA_RADIUS_M = 15


def _dem_preview_mean(database_name: str, area_ewkt: str) -> float:
    """Return the mean of the job DEM preview clipped to ``area_ewkt``."""
    credentials = db_utils.get_job_admin_credentials(database_name)
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return connection.execute(
            sqlmodel.text(
                "SELECT (ST_SummaryStats(ST_Union("
                "  ST_Clip(rast, ST_GeomFromEWKT(:area), true)"
                "))).mean "
                "FROM user_data.dem_preview "
                "WHERE ST_Intersects(rast, ST_GeomFromEWKT(:area))"
            ).bindparams(area=area_ewkt)
        ).scalar_one()


def _update_area_dirty(database_name: str) -> bool:
    """Return the ``dirty`` flag of the single update area in the job database."""
    credentials = db_utils.get_job_admin_credentials(database_name)
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return connection.execute(
            sqlmodel.text("SELECT dirty FROM user_data.update_area")
        ).scalar_one()


@pytest.fixture
def dissolve_update_area_setup(
    request: "pytest.FixtureRequest",
    seeded_processing_dem: int,
    created_db: str,
    db: "Session",
) -> str:
    """Provision the job database for a dissolve run without the DEM workflow.

    ``seeded_processing_dem`` populates the primary ``dem.dem`` table. This fixture
    then provisions a job database the way the orchestrator DAG would, copies the
    primary DEM into ``user_data.dem_preview``, seeds a distinct constant-valued
    ``reference.dem`` and creates an update area polygon. Returns the update area
    geometry as EWKT so the test can probe the preview inside it.

    The update area is seeded ``dirty`` by default; parametrize the fixture
    indirectly with ``False`` to seed a clean area that the dissolve DAG must skip.
    """
    dirty = getattr(request, "param", True)
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None

    # The orchestrator DAG normally provisions the job db and stamps
    # database_name; do the same by hand so the dissolve DAG's precondition holds.
    database_name = f"job_{production_area.id}"
    production_area.database_name = database_name
    db.add(production_area)
    db.commit()

    with engine_utils.get_autocommit_connection(
        db_utils.get_job_admin_credentials("postgres")
    ) as admin_connection:
        database_utils.initialize_db_from_template(
            admin_connection, database_name, replace_existing=True
        )

    primary = db_utils.get_primary_admin_credentials(created_db)
    job = db_utils.get_job_admin_credentials(database_name)
    with (
        engine_utils.get_autocommit_connection(primary) as primary_connection,
        engine_utils.get_autocommit_connection(job) as job_connection,
    ):
        tiles = (
            primary_connection.execute(sqlmodel.text("SELECT rast::text FROM dem.dem"))
            .scalars()
            .all()
        )
        assert tiles, "No primary DEM tiles were seeded"
        for tile in tiles:
            # Copy the primary DEM verbatim into the preview.
            job_connection.execute(
                sqlmodel.text(
                    "INSERT INTO user_data.dem_preview (rast) "
                    "VALUES (CAST(:rast AS raster))"
                ).bindparams(rast=tile)
            )
            # Seed the reference DEM as a flat surface at REFERENCE_DEM_VALUE,
            # keeping the nodata mask, so it is clearly distinct from the preview.
            job_connection.execute(
                sqlmodel.text(
                    "INSERT INTO reference.dem (rast) "
                    "VALUES (ST_MapAlgebra(CAST(:rast AS raster), 1, '32BF', :value))"
                ).bindparams(rast=tile, value=str(REFERENCE_DEM_VALUE))
            )

        area_ewkt = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Buffer(ST_Centroid(ST_Union(rast::geometry)), "
                ":radius)) FROM user_data.dem_preview"
            ).bindparams(radius=UPDATE_AREA_RADIUS_M)
        ).scalar_one()
        job_connection.execute(
            sqlmodel.text(
                "INSERT INTO user_data.update_area (id, geom, dirty) "
                "VALUES (gen_random_uuid(), ST_GeomFromEWKT(:geom), :dirty)"
            ).bindparams(geom=area_ewkt, dirty=dirty)
        )

    return area_ewkt


@pytest.mark.xdist_group("airflow")
def test_dissolve_update_areas_workflow(
    qgis_plugin: "Plugin",
    qtbot: "QtBot",
    m_error_dialog: "MagicMock",
    airflow_client: "AirflowClient",
    db: "Session",
    dissolve_update_area_setup: str,
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )

    area_ewkt = dissolve_update_area_setup
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    database_name = production_area.database_name
    assert database_name is not None

    # The preview starts from the primary DEM, i.e. the real elevations, well
    # below the flat reference surface it should be dissolved to.
    mean_before = _dem_preview_mean(database_name, area_ewkt)
    assert mean_before != pytest.approx(REFERENCE_DEM_VALUE, abs=100)

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    assert production_area_layer.featureCount() == 1
    action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_START_DISSOLVE_UPDATE_AREAS,
    )
    feature = next(production_area_layer.getFeatures())

    client = api_client.get_api_client()
    with qtbot.waitSignal(client.workflow_started, timeout=10000) as blocker:
        layers.run_layer_action(production_area_layer, action, feature)
        dag_id, dag_run_id = blocker.args

    m_error_dialog.assert_not_called()
    dag_run = DagRun(id=dag_id, run_id=dag_run_id)

    state = airflow_client.wait_for_dag_run(dag_run, timeout=WORKFLOW_TIMEOUT_S)
    assert state == "success", (
        f"DAG run finished with state={state}\n"
        f"{airflow_client.describe_failed_run(dag_run)}"
    )

    # The dissolve unions the reference DEM (priority) into the preview inside the
    # update area, so the preview must now match the flat reference surface.
    mean_after = _dem_preview_mean(database_name, area_ewkt)
    assert mean_after == pytest.approx(REFERENCE_DEM_VALUE, abs=50)
    assert abs(mean_after - mean_before) > 100

    # The worker clears the dirty flag once the area is dissolved, and the dirty
    # trigger leaves the worker's own update alone, so the area ends up clean.
    assert _update_area_dirty(database_name) is False

    # The workflow stamps the production area processing status COMPLETED on success.
    db.expire_all()
    completed_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert completed_area is not None
    assert completed_area.processing_status == ProcessingStatus.COMPLETED


@pytest.mark.xdist_group("airflow")
@pytest.mark.parametrize("dissolve_update_area_setup", [False], indirect=True)
def test_dissolve_skips_clean_update_areas(
    qgis_plugin: "Plugin",
    qtbot: "QtBot",
    m_error_dialog: "MagicMock",
    airflow_client: "AirflowClient",
    db: "Session",
    dissolve_update_area_setup: str,
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )

    area_ewkt = dissolve_update_area_setup
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    database_name = production_area.database_name
    assert database_name is not None

    # The single update area is seeded clean, so the DAG must dissolve nothing and
    # leave the preview at the original DEM elevations.
    mean_before = _dem_preview_mean(database_name, area_ewkt)
    assert mean_before != pytest.approx(REFERENCE_DEM_VALUE, abs=100)

    production_area_layer = layers.get_vector_layer_by_model(ProductionArea)
    action = layers.find_layer_action(
        production_area_layer,
        management_layer_collection.ACTION_TITLE_START_DISSOLVE_UPDATE_AREAS,
    )
    feature = next(production_area_layer.getFeatures())

    client = api_client.get_api_client()
    with qtbot.waitSignal(client.workflow_started, timeout=10000) as blocker:
        layers.run_layer_action(production_area_layer, action, feature)
        dag_id, dag_run_id = blocker.args

    m_error_dialog.assert_not_called()
    dag_run = DagRun(id=dag_id, run_id=dag_run_id)

    state = airflow_client.wait_for_dag_run(dag_run, timeout=WORKFLOW_TIMEOUT_S)
    assert state == "success", (
        f"DAG run finished with state={state}\n"
        f"{airflow_client.describe_failed_run(dag_run)}"
    )

    # No dirty areas means no dissolve ran: the preview is untouched and the clean
    # area stays clean.
    mean_after = _dem_preview_mean(database_name, area_ewkt)
    assert mean_after == pytest.approx(mean_before, abs=1)
    assert _update_area_dirty(database_name) is False
