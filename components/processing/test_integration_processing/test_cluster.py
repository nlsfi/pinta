# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

import pytest
from pinta_common import Settings
from pinta_db.job_db.models import reference
from sqlmodel import select

from pinta_processing.scripts import cluster

if typing.TYPE_CHECKING:
    from sqlmodel import Session

# Base coordinates in the DB CRS (EPSG:3067). Individual polygons are placed
# relative to this origin so their spatial relationships are easy to reason about.
BASE_X = 500000
BASE_Y = 7000000


def _square(x0: float, y0: float, size: float) -> str:
    """Build an EWKT square polygon anchored at the base origin."""
    x, y = BASE_X + x0, BASE_Y + y0
    return (
        f"SRID={Settings.DB_SRID};POLYGON(("
        f"{x} {y}, {x + size} {y}, {x + size} {y + size}, "
        f"{x} {y + size}, {x} {y}))"
    )


def _add_polygon(
    session: "Session",
    *,
    x0: float,
    y0: float,
    size: float,
    relevance_score: float,
    energy_sum: float,
) -> None:
    session.add(
        reference.DiffPolygon(
            relevance_score=relevance_score,
            energy_sum=energy_sum,
            geom=_square(x0, y0, size),
        )
    )


def _clusters(session: "Session") -> list[reference.UpdateAreaSuggestion]:
    return list(session.exec(select(reference.UpdateAreaSuggestion)).all())


def test_clusters_adjacent_polygons_and_sums_energy(
    processing_worker_session: "Session",
) -> None:
    """Adjacent polygons merge into one cluster with summed per-polygon energy."""
    # Two adjacent 30x30 squares sharing an edge -> one cluster, union area 1800.
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=0,
        size=30,
        relevance_score=10,
        energy_sum=100,
    )
    _add_polygon(
        processing_worker_session,
        x0=30,
        y0=0,
        size=30,
        relevance_score=10,
        energy_sum=200,
    )
    # An isolated 30x30 square far away -> its own cluster, area exactly 900.
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=1000,
        size=30,
        relevance_score=10,
        energy_sum=50,
    )
    # Small isolated polygon below the minimum cluster area -> dropped.
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=2000,
        size=10,
        relevance_score=10,
        energy_sum=999,
    )
    # Low relevance polygons sit under the 25th percentile threshold -> excluded.
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=3000,
        size=30,
        relevance_score=0,
        energy_sum=999,
    )
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=4000,
        size=30,
        relevance_score=0,
        energy_sum=999,
    )
    processing_worker_session.commit()

    cluster.cluster_diff_polygons(processing_worker_session)

    clusters = _clusters(processing_worker_session)
    assert len(clusters) == 2

    by_energy = {round(c.energy_sum): c for c in clusters}
    assert set(by_energy) == {300, 50}

    # pixel_area = DB_DEM_PIXEL_SIZE ** 2 = 2 ** 2 = 4.
    merged = by_energy[300]
    assert merged.cluster_area == pytest.approx(1800)
    assert merged.energy_distribution == pytest.approx(300 * 4 / 1800)
    assert merged.geom is not None

    isolated = by_energy[50]
    assert isolated.cluster_area == pytest.approx(900)
    assert isolated.energy_distribution == pytest.approx(50 * 4 / 900)


def test_scales_energy_distribution_by_pixel_area(
    processing_worker_session: "Session",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Energy density uses the DEM pixel area (pixel size squared)."""
    monkeypatch.setenv("DB_DEM_PIXEL_SIZE", "3")

    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=0,
        size=30,
        relevance_score=10,
        energy_sum=100,
    )
    # A low relevance polygon keeps the 25th percentile threshold below the target.
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=1000,
        size=30,
        relevance_score=0,
        energy_sum=0,
    )
    processing_worker_session.commit()

    cluster.cluster_diff_polygons(processing_worker_session)

    clusters = _clusters(processing_worker_session)
    assert len(clusters) == 1
    # pixel_area = 3 ** 2 = 9, cluster area = 900.
    assert clusters[0].energy_distribution == pytest.approx(100 * 9 / 900)


def test_replaces_existing_clusters(
    processing_worker_session: "Session",
) -> None:
    """Running the clustering truncates previously stored clusters."""
    processing_worker_session.add(
        reference.UpdateAreaSuggestion(
            energy_sum=1.0,
            energy_distribution=1.0,
            cluster_area=1.0,
            geom=_square(0, 0, 10),
        )
    )
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=0,
        size=30,
        relevance_score=10,
        energy_sum=100,
    )
    _add_polygon(
        processing_worker_session,
        x0=0,
        y0=1000,
        size=30,
        relevance_score=0,
        energy_sum=0,
    )
    processing_worker_session.commit()

    cluster.cluster_diff_polygons(processing_worker_session)

    clusters = _clusters(processing_worker_session)
    assert len(clusters) == 1
    assert clusters[0].energy_sum == pytest.approx(100)


def test_no_polygons_produces_no_clusters(
    processing_worker_session: "Session",
) -> None:
    """Clustering with no source polygons leaves an empty cluster table."""
    cluster.cluster_diff_polygons(processing_worker_session)

    assert _clusters(processing_worker_session) == []
