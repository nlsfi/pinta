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
# so the buffered primary DEM read stays inside the seeded coverage.
UPDATE_AREA_RADIUS_M = 15

# Constant elevation set on the second update area. Distinct from both the real
# DEM range and REFERENCE_DEM_VALUE, so a mean over the area tells a preview
# masked to the elevation apart from one dissolved from the reference DEM.
UPDATE_AREA_ELEVATION = 500.0

# Offset (m) of the elevation update area east of the DEM centroid, far enough
# that the two areas and their buffered dissolve reads do not overlap while
# staying inside the seeded coverage.
ELEVATION_AREA_OFFSET_M = 100


# Minimum distance (m) the edge update area must keep from the two centroid
# areas so their buffered dissolve reads and writes never touch the same tiles.
EDGE_AREA_MIN_SEPARATION_M = 60

# Offset (m) of the coverage gap probe west of the deleted preview tile's east
# edge: far enough that the dissolve seam never writes there, so the probe sees
# pixels that can only come from the dynamically copied primary DEM tile.
GAP_PROBE_OFFSET_M = 80

# Radius (m) of the coverage gap probe polygon.
GAP_PROBE_RADIUS_M = 10


class DissolveSetup(typing.NamedTuple):
    """Geometries (EWKT) and expectations seeded for the dissolve tests."""

    area_ewkt: str
    elevation_area_ewkt: str
    # Update area straddling the edge of the initialized preview coverage: its
    # west half lies on a preview tile deleted from the fixture.
    edge_area_ewkt: str
    # Probe inside the deleted preview tile but outside the dissolve seam.
    gap_probe_ewkt: str
    # Primary DEM mean over the probe, the value a verbatim tile copy restores.
    gap_probe_primary_mean: float
    # Probe inside a nodata pocket punched into an existing preview tile under
    # the edge area, the way partially initialized boundary tiles look.
    pocket_probe_ewkt: str
    # Primary DEM mean over the pocket, the value the fill upsert restores.
    pocket_probe_primary_mean: float


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


def _dem_preview_tile_count(database_name: str, area_ewkt: str) -> int:
    """Return the number of job DEM preview tiles intersecting ``area_ewkt``."""
    credentials = db_utils.get_job_admin_credentials(database_name)
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return connection.execute(
            sqlmodel.text(
                "SELECT count(*) FROM user_data.dem_preview "
                "WHERE ST_Intersects(rast, ST_GeomFromEWKT(:area))"
            ).bindparams(area=area_ewkt)
        ).scalar_one()


def _update_area_dirty(database_name: str, area_ewkt: str) -> bool:
    """Return the ``dirty`` flag of the update area with the given geometry."""
    credentials = db_utils.get_job_admin_credentials(database_name)
    with engine_utils.get_autocommit_connection(credentials) as connection:
        return connection.execute(
            sqlmodel.text(
                "SELECT dirty FROM user_data.update_area "
                "WHERE ST_Equals(geom, ST_GeomFromEWKT(:area))"
            ).bindparams(area=area_ewkt)
        ).scalar_one()


@pytest.fixture
def dissolve_update_area_setup(
    request: "pytest.FixtureRequest",
    seeded_processing_dem: int,
    created_db: str,
    db: "Session",
) -> DissolveSetup:
    """Provision the job database for a dissolve run without the DEM workflow.

    ``seeded_processing_dem`` populates the primary ``dem.dem`` table. This fixture
    then provisions a job database the way the orchestrator DAG would, copies the
    primary DEM into ``user_data.dem_preview``, seeds a distinct constant-valued
    ``reference.dem`` and creates three update area polygons: one over the DEM
    centroid that dissolves from the reference DEM, one ELEVATION_AREA_OFFSET_M
    east of it with a constant elevation set that the dissolve must mask flat
    without reading the reference DEM, and one straddling a preview coverage
    gap: the westernmost preview tile under it is deleted again, the way an
    update area reaching outside the production area lands on preview tiles
    that were never initialized. Returns the update area geometries as EWKT
    plus a probe polygon (and its expected primary DEM mean) inside the gap so
    the test can verify the dissolve copies the missing tile back in.

    The update areas are seeded ``dirty`` by default; parametrize the fixture
    indirectly with ``False`` to seed clean areas that the dissolve DAG must skip.
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

        elevation_area_ewkt = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Buffer(ST_Translate("
                "ST_Centroid(ST_Union(rast::geometry)), :offset, 0), :radius)) "
                "FROM user_data.dem_preview"
            ).bindparams(offset=ELEVATION_AREA_OFFSET_M, radius=UPDATE_AREA_RADIUS_M)
        ).scalar_one()
        job_connection.execute(
            sqlmodel.text(
                "INSERT INTO user_data.update_area (id, geom, elevation, dirty) "
                "VALUES (gen_random_uuid(), ST_GeomFromEWKT(:geom), :elevation, "
                ":dirty)"
            ).bindparams(
                geom=elevation_area_ewkt,
                elevation=UPDATE_AREA_ELEVATION,
                dirty=dirty,
            )
        )

        # Pick the gap tile to delete from the preview: the westernmost tile
        # column, vertically closest to the coverage centre. Its east edge
        # midpoint becomes the centre of the edge update area, so the area
        # straddles the deleted tile and its still-initialized east neighbor.
        gap_ulx, gap_uly, gap_span = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_UpperLeftX(rast), ST_UpperLeftY(rast), "
                "ST_ScaleX(rast) * ST_Width(rast) "
                "FROM user_data.dem_preview "
                "ORDER BY ST_UpperLeftX(rast), ABS(ST_UpperLeftY(rast) - ("
                "  SELECT ST_Y(ST_Centroid(ST_Union(rast::geometry))) "
                "  FROM user_data.dem_preview)) "
                "LIMIT 1"
            )
        ).one()

        east_neighbor_exists = job_connection.execute(
            sqlmodel.text(
                "SELECT EXISTS (SELECT 1 FROM user_data.dem_preview "
                "WHERE ST_UpperLeftX(rast) = :x AND ST_UpperLeftY(rast) = :y)"
            ).bindparams(x=gap_ulx + gap_span, y=gap_uly)
        ).scalar_one()
        assert east_neighbor_exists, (
            "Seeded DEM coverage is only one tile column wide; the edge update "
            "area cannot straddle the preview coverage gap"
        )

        edge_area_ewkt = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Buffer(ST_SetSRID("
                "ST_MakePoint(:x, :y), ST_SRID(rast)), :radius)) "
                "FROM user_data.dem_preview LIMIT 1"
            ).bindparams(
                x=gap_ulx + gap_span,
                y=gap_uly - gap_span / 2,
                radius=UPDATE_AREA_RADIUS_M,
            )
        ).scalar_one()
        gap_probe_ewkt = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Buffer(ST_SetSRID("
                "ST_MakePoint(:x, :y), ST_SRID(rast)), :radius)) "
                "FROM user_data.dem_preview LIMIT 1"
            ).bindparams(
                x=gap_ulx + gap_span - GAP_PROBE_OFFSET_M,
                y=gap_uly - gap_span / 2,
                radius=GAP_PROBE_RADIUS_M,
            )
        ).scalar_one()

        # A nodata pocket punched into the east neighbor tile, inside the
        # dissolve footprint's tile but away from the seam: this is how a
        # partially initialized tile at the production area boundary looks.
        pocket_probe_ewkt = job_connection.execute(
            sqlmodel.text(
                "SELECT ST_AsEWKT(ST_Buffer(ST_SetSRID("
                "ST_MakePoint(:x, :y), ST_SRID(rast)), :radius)) "
                "FROM user_data.dem_preview LIMIT 1"
            ).bindparams(
                x=gap_ulx + 2 * gap_span - GAP_PROBE_OFFSET_M,
                y=gap_uly - gap_span / 2,
                radius=GAP_PROBE_RADIUS_M,
            )
        ).scalar_one()

        # The gap tile and the nodata pocket must be far enough from the other
        # two update areas that they cannot disturb their preview probes or
        # dissolve reads.
        for other_ewkt in (area_ewkt, elevation_area_ewkt):
            for probe_ewkt in (edge_area_ewkt, pocket_probe_ewkt):
                separation = job_connection.execute(
                    sqlmodel.text(
                        "SELECT ST_Distance("
                        "ST_GeomFromEWKT(:probe), ST_GeomFromEWKT(:other))"
                    ).bindparams(probe=probe_ewkt, other=other_ewkt)
                ).scalar_one()
                assert separation > EDGE_AREA_MIN_SEPARATION_M, (
                    "The edge update area or its nodata pocket is too close "
                    "to the centroid update areas"
                )

        # The means the copy and the fill upsert must restore under the probes.
        def primary_dem_mean(area_ewkt: str) -> float:
            return primary_connection.execute(
                sqlmodel.text(
                    "SELECT (ST_SummaryStats(ST_Union("
                    "  ST_Clip(rast, ST_GeomFromEWKT(:area), true)"
                    "))).mean "
                    "FROM dem.dem WHERE ST_Intersects(rast, ST_GeomFromEWKT(:area))"
                ).bindparams(area=area_ewkt)
            ).scalar_one()

        gap_probe_primary_mean = primary_dem_mean(gap_probe_ewkt)
        assert gap_probe_primary_mean is not None, (
            "The seeded primary DEM has no data under the coverage gap probe"
        )
        pocket_probe_primary_mean = primary_dem_mean(pocket_probe_ewkt)
        assert pocket_probe_primary_mean is not None, (
            "The seeded primary DEM has no data under the nodata pocket probe"
        )

        job_connection.execute(
            sqlmodel.text(
                "DELETE FROM user_data.dem_preview "
                "WHERE ST_UpperLeftX(rast) = :x AND ST_UpperLeftY(rast) = :y"
            ).bindparams(x=gap_ulx, y=gap_uly)
        )
        # Punch the nodata pocket into the east neighbor tile: keep the tile
        # extent but blank the pixels inside the pocket.
        job_connection.execute(
            sqlmodel.text(
                "UPDATE user_data.dem_preview "
                "SET rast = ST_Clip(rast, "
                "  ST_Difference(rast::geometry, ST_GeomFromEWKT(:pocket)), "
                "  ST_BandNoDataValue(rast, 1), false) "
                "WHERE ST_UpperLeftX(rast) = :x AND ST_UpperLeftY(rast) = :y"
            ).bindparams(
                pocket=pocket_probe_ewkt,
                x=gap_ulx + gap_span,
                y=gap_uly,
            )
        )
        job_connection.execute(
            sqlmodel.text(
                "INSERT INTO user_data.update_area (id, geom, dirty) "
                "VALUES (gen_random_uuid(), ST_GeomFromEWKT(:geom), :dirty)"
            ).bindparams(geom=edge_area_ewkt, dirty=dirty)
        )

    return DissolveSetup(
        area_ewkt=area_ewkt,
        elevation_area_ewkt=elevation_area_ewkt,
        edge_area_ewkt=edge_area_ewkt,
        gap_probe_ewkt=gap_probe_ewkt,
        gap_probe_primary_mean=gap_probe_primary_mean,
        pocket_probe_ewkt=pocket_probe_ewkt,
        pocket_probe_primary_mean=pocket_probe_primary_mean,
    )


@pytest.mark.smoke
@pytest.mark.xdist_group("airflow")
def test_dissolve_update_areas_workflow(
    qgis_plugin: "Plugin",
    qtbot: "QtBot",
    m_error_dialog: "MagicMock",
    airflow_client: "AirflowClient",
    db: "Session",
    dissolve_update_area_setup: DissolveSetup,
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )

    area_ewkt = dissolve_update_area_setup.area_ewkt
    elevation_area_ewkt = dissolve_update_area_setup.elevation_area_ewkt
    edge_area_ewkt = dissolve_update_area_setup.edge_area_ewkt
    gap_probe_ewkt = dissolve_update_area_setup.gap_probe_ewkt
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    database_name = production_area.database_name
    assert database_name is not None

    # The preview starts from the primary DEM, i.e. the real elevations, well
    # below the flat reference surface it should be dissolved to.
    mean_before = _dem_preview_mean(database_name, area_ewkt)
    assert mean_before != pytest.approx(REFERENCE_DEM_VALUE, abs=100)
    elevation_mean_before = _dem_preview_mean(database_name, elevation_area_ewkt)
    assert elevation_mean_before != pytest.approx(UPDATE_AREA_ELEVATION, abs=100)

    # The edge area's west half sits on a preview coverage gap: no tile at all.
    assert _dem_preview_tile_count(database_name, gap_probe_ewkt) == 0

    # The east neighbor tile exists but its nodata pocket holds no values, the
    # way a partially initialized tile at the production area boundary looks.
    assert (
        _dem_preview_mean(database_name, dissolve_update_area_setup.pocket_probe_ewkt)
        is None
    )

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

    # The area with a constant elevation set skips the reference DEM (a flat
    # surface at REFERENCE_DEM_VALUE, which would fail this check) and is masked
    # flat to its own elevation instead.
    elevation_mean_after = _dem_preview_mean(database_name, elevation_area_ewkt)
    assert elevation_mean_after == pytest.approx(UPDATE_AREA_ELEVATION, abs=50)
    assert abs(elevation_mean_after - elevation_mean_before) > 100

    # The dissolve copied the missing preview tile from the primary DEM before
    # merging, so the edge area dissolves to the reference surface on both
    # halves and the rest of the copied tile carries the primary elevations
    # verbatim instead of staying a nodata hole.
    edge_mean_after = _dem_preview_mean(database_name, edge_area_ewkt)
    assert edge_mean_after == pytest.approx(REFERENCE_DEM_VALUE, abs=50)
    assert _dem_preview_tile_count(database_name, gap_probe_ewkt) == 1
    gap_probe_mean = _dem_preview_mean(database_name, gap_probe_ewkt)
    assert gap_probe_mean == pytest.approx(
        dissolve_update_area_setup.gap_probe_primary_mean, abs=0.01
    )

    # The partially filled east neighbor tile was upserted in fill mode: the
    # nodata pocket now carries the primary DEM values.
    pocket_probe_mean = _dem_preview_mean(
        database_name, dissolve_update_area_setup.pocket_probe_ewkt
    )
    assert pocket_probe_mean == pytest.approx(
        dissolve_update_area_setup.pocket_probe_primary_mean, abs=0.01
    )

    # The worker clears the dirty flags once the areas are dissolved, and the
    # dirty trigger leaves the worker's own update alone, so all end up clean.
    assert _update_area_dirty(database_name, area_ewkt) is False
    assert _update_area_dirty(database_name, elevation_area_ewkt) is False
    assert _update_area_dirty(database_name, edge_area_ewkt) is False

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
    dissolve_update_area_setup: DissolveSetup,
) -> None:
    # Importing here to avoid wrong DB name in environment
    from pinta_qgis_plugin.api import api_client  # noqa: PLC0415
    from pinta_qgis_plugin.project.groups import (  # noqa: PLC0415
        management_layer_collection,
    )

    area_ewkt = dissolve_update_area_setup.area_ewkt
    elevation_area_ewkt = dissolve_update_area_setup.elevation_area_ewkt
    production_area = db.exec(sqlmodel.select(ProductionArea)).first()
    assert production_area is not None
    database_name = production_area.database_name
    assert database_name is not None

    # Both update areas are seeded clean, so the DAG must dissolve nothing and
    # leave the preview at the original DEM elevations.
    mean_before = _dem_preview_mean(database_name, area_ewkt)
    assert mean_before != pytest.approx(REFERENCE_DEM_VALUE, abs=100)
    elevation_mean_before = _dem_preview_mean(database_name, elevation_area_ewkt)

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

    # No dirty areas means no dissolve ran: the preview is untouched (also in
    # the elevation area) and the clean areas stay clean.
    mean_after = _dem_preview_mean(database_name, area_ewkt)
    assert mean_after == pytest.approx(mean_before, abs=1)
    elevation_mean_after = _dem_preview_mean(database_name, elevation_area_ewkt)
    assert elevation_mean_after == pytest.approx(elevation_mean_before, abs=1)
    assert _update_area_dirty(database_name, area_ewkt) is False
    assert _update_area_dirty(database_name, elevation_area_ewkt) is False

    # The preview coverage gap is only filled when an area is dissolved, so
    # skipping the clean edge area must leave the gap empty.

    # The preview coverage gap and the nodata pocket are only filled when an
    # area is dissolved, so skipping the clean edge area must leave both as is.
    assert (
        _dem_preview_tile_count(
            database_name, dissolve_update_area_setup.gap_probe_ewkt
        )
        == 0
    )
    assert (
        _dem_preview_mean(database_name, dissolve_update_area_setup.pocket_probe_ewkt)
        is None
    )
