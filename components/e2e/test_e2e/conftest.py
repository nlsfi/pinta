# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import typing
from collections.abc import Iterator

import pytest
import qgis.utils
import sqlmodel
from pinta_db.primary_db.models.management import ProductionArea
from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils
from pinta_db_utils.postgis import raster
from pinta_e2e_utils import constants
from pinta_e2e_utils.airflow_client import AirflowClient
from pinta_qgis_plugin.utils import messages
from pinta_test_utils import xdist_utils
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

if typing.TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pinta_qgis_plugin.plugin import Plugin
    from pytest_mock import MockerFixture
    from qgis.gui import QgisInterface
    from sqlmodel import Session

"""
!!! IMPORTANT !!!
DO NOT import anything that imports qgis.utils.iface
(or some module that imports other module that imports it) in conftest root!
Importing those modules in fixtures is OK.

The same goes with pinta_qgis_plugin.env.py.
"""

DEFAULT_BACKEND_URL = "http://localhost:3011"
DEFAULT_AIRFLOW_URL = "http://localhost:8080"
DEFAULT_AIRFLOW_ADMIN_USERNAME = "admin"
DEFAULT_AIRFLOW_ADMIN_PASSWORD = "admin"

PROCESSING_WORKER_DB_CONN_ID = "pinta_processing_db"
PROCESS_PRODUCTION_AREAS_DAG_ID = "process_production_areas"
PRODUCTION_AREA_VARIABLE = "production_area_1"
DAG_RUN_TIMEOUT_S = 60.0 * 5


def pytest_configure(config: pytest.Config):
    os.environ.setdefault("PINTA_DEVELOPMENT_MODE", "true")


@pytest.hookimpl
def pytest_xdist_auto_num_workers(config: "pytest.Config"):
    return xdist_utils.get_number_of_workers(config)


@pytest.fixture
def _set_env_variables(
    created_db: str,
    worker_id: str,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """Set test specific environment variables."""
    monkeypatch.setenv("DB_PRIMARY_NAME", created_db)
    monkeypatch.setenv("DB_SRID", constants.SRID)
    monkeypatch.delenv("PINTA_BASE_MAP_LAYER_CONFIG", raising=False)
    monkeypatch.setenv("PINTA_INITIAL_PROJECT_EXTENT", "67734,6570084,843161,7879314")


@pytest.fixture(scope="session")
def _primary_db(worker_id: str) -> str:
    """Clone the primary db once per worker."""
    return db_utils.create_primary_db(worker_id)


@pytest.fixture(scope="session")
def _provisioned_job_dbs(_primary_db: str) -> Iterator[set[str]]:
    """Drop the job databases provisioned during the run when the session ends."""
    job_dbs: set[str] = set()
    try:
        yield job_dbs
    finally:
        job_dbs.update(db_utils.get_job_database_names(_primary_db))
        db_utils.drop_job_databases(job_dbs)


@pytest.fixture
def created_db(_primary_db: str, _provisioned_job_dbs: set[str]) -> str:
    """Return the worker's primary db clone, emptied for this test."""
    _provisioned_job_dbs.update(db_utils.get_job_database_names(_primary_db))
    db_utils.reset_primary_db(_primary_db)
    return _primary_db


@pytest.fixture
def backend_db_override_headers(created_db: str) -> dict[str, str]:
    """Headers pointing the backend at this test's per-worker db clone."""
    return {"X-Pinta-Db-Name": created_db}


@pytest.fixture
def db(created_db: str) -> Iterator["Session"]:
    with engine_utils.get_session(
        db_utils.get_primary_writer_credentials(created_db)
    ) as session:
        yield session


@pytest.fixture
def qgis_plugin(
    _set_env_variables: None,
    qgis_new_project: None,
    qgis_iface: "QgisInterface",
    tmp_path: "Path",
) -> typing.Generator["Plugin", None, None]:
    """Initialize and return the plugin object."""
    from pinta_qgis_plugin import classFactory

    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(constants.SRID))
    plugin = classFactory(qgis_iface)
    qgis.utils.plugins["pinta"] = plugin

    plugin.initGui()
    yield plugin
    plugin.unload()


@pytest.fixture
def m_error_dialog(mocker: "MockerFixture") -> "MagicMock":
    return mocker.patch.object(messages, "show_error_dialog")


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Base URL of the containerized pinta backend."""
    return os.environ.get("PINTA_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


@pytest.fixture(scope="session")
def airflow_url() -> str:
    """Base URL of the containerized Airflow API."""
    return os.environ.get("PINTA_BACKEND_AIRFLOW_BASE_URL", DEFAULT_AIRFLOW_URL).rstrip(
        "/"
    )


@pytest.fixture(scope="session")
def airflow_client(airflow_url: str) -> AirflowClient:
    """Admin-authenticated Airflow API client (cached for the session)."""
    return AirflowClient.login(
        airflow_url,
        DEFAULT_AIRFLOW_ADMIN_USERNAME,
        os.environ.get("AIRFLOW_ADMIN_PASSWORD", DEFAULT_AIRFLOW_ADMIN_PASSWORD),
    )


@pytest.fixture
def _processing_db_pointing_at_test_db(
    airflow_client: AirflowClient,
    created_db: str,
) -> Iterator[None]:
    """Point the worker-DB Airflow connection at this test's per-worker clone.

    Restored on teardown so other tests / dev runs see the original schema.
    """
    original = airflow_client.get_connection(PROCESSING_WORKER_DB_CONN_ID)
    airflow_client.patch_connection(
        PROCESSING_WORKER_DB_CONN_ID, fields={"schema": created_db}
    )
    try:
        yield
    finally:
        airflow_client.patch_connection(
            PROCESSING_WORKER_DB_CONN_ID,
            fields={"schema": original.schema},
        )


@pytest.fixture
def processed_production_areas(
    airflow_client: AirflowClient,
    _processing_db_pointing_at_test_db: None,
) -> None:
    """Run the process_production_areas DAG."""
    # The sensor only flags a folder as changed when its stored hash differs,
    # so clear any leftover hash to guarantee a fresh run.
    airflow_client.delete_variable(PRODUCTION_AREA_VARIABLE)

    run = airflow_client.trigger_dag_run(PROCESS_PRODUCTION_AREAS_DAG_ID)
    state = airflow_client.wait_for_dag_run(
        run,
        timeout=DAG_RUN_TIMEOUT_S,
    )
    if state != "success":
        pytest.fail(
            f"DAG run finished with state={state}\n"
            + airflow_client.describe_failed_run(run)
        )


@pytest.fixture
def reduce_point_cloud_tiles(
    processed_production_areas: None,
    db: "Session",
) -> None:
    """Delete most point cloud tiles in the test database."""
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None

    for tile in sorted(production_area.tiles, key=lambda tile: tile.file_path)[2:]:
        db.delete(tile)
    db.commit()

    assert len(db.exec(sqlmodel.select(ProductionArea)).first().tiles) == 2


@pytest.fixture
def seeded_processing_dem(
    reduce_point_cloud_tiles: None,
    created_db: str,
) -> int:
    """Seed the cloned DEM schema with tiles overlapping the production area.

    The clone is truncated on creation, but calculating a DEM diff needs an
    existing DEM to compare the freshly computed reference DEM against, and the
    dissolve copies missing preview tiles (base and overviews) from the primary
    DEM, so copy the relevant tiles of every DEM table from the source primary
    database. Returns the number of seeded base tiles.
    """
    source_db = created_db.rsplit("_test_", 1)[0]
    source = db_utils.get_primary_admin_credentials(source_db)
    destination = db_utils.get_primary_admin_credentials(created_db)
    dem_tables = [
        "dem",
        *(
            raster.OVERVIEW_TABLE_NAME.format(level=level, table_name="dem")
            for level in raster.DEFAULT_OVERVIEW_LEVELS
        ),
    ]
    with (
        engine_utils.get_autocommit_connection(source) as source_connection,
        engine_utils.get_autocommit_connection(destination) as destination_connection,
    ):
        area_ewkt = destination_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Envelope(geom)) "
                "FROM management.production_area LIMIT 1"
            )
        ).scalar_one()
        seeded_tiles = {}
        for table in dem_tables:
            tiles = (
                source_connection.execute(
                    sqlmodel.text(
                        f"SELECT rast::text FROM dem.{table} "
                        "WHERE ST_Intersects(rast::geometry, ST_GeomFromEWKT(:area))"
                    ).bindparams(area=area_ewkt)
                )
                .scalars()
                .all()
            )
            for tile in tiles:
                destination_connection.execute(
                    sqlmodel.text(
                        f"INSERT INTO dem.{table} (rast) VALUES (CAST(:rast AS raster))"
                    ).bindparams(rast=tile)
                )
            seeded_tiles[table] = len(tiles)
    for table in dem_tables:
        assert seeded_tiles[table], f"No source dem.{table} tiles overlap the area"
    return seeded_tiles["dem"]
