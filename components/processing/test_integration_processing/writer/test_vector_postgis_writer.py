# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from collections.abc import Iterator

import geopandas
import psycopg.errors
import pytest
import sqlalchemy as sa
from shapely.geometry import Point

from pinta_processing import core
from pinta_processing.writer import VectorPostgisWriter

if typing.TYPE_CHECKING:
    from sqlmodel import Session

_SCHEMA = "user_data"
_TABLE = "test_vector_output"


@pytest.fixture
def test_table(processing_worker_session: "Session") -> Iterator[None]:
    """Create a temporary table with non-geometry columns, rollback after the test."""
    processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(
            f"""
            CREATE TABLE {_SCHEMA}.{_TABLE} (
                id    SERIAL PRIMARY KEY,
                name  TEXT NOT NULL,
                score DOUBLE PRECISION,
                geom  geometry(Point, 3067)
            )
            """
        )
    )
    yield
    processing_worker_session.rollback()


def test_vector_postgis_writer_writes_non_geometry_fields(
    processing_worker_session: "Session", test_table: None
) -> None:
    """Non-geometry columns in the GeoDataFrame are persisted to the DB."""
    gdf = geopandas.GeoDataFrame(
        {"name": ["alpha", "beta"], "score": [1.5, 2.5]},
        geometry=[Point(385000, 6672000), Point(386000, 6673000)],
        crs="EPSG:3067",
    )
    gdf.rename_geometry("geom", inplace=True)
    stage = VectorPostgisWriter(_SCHEMA, _TABLE, processing_worker_session)
    stage.process(core.VectorDataset(geodataframe=gdf))

    rows = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT name, score FROM {_SCHEMA}.{_TABLE} ORDER BY name")
    ).all()

    assert rows == [("alpha", 1.5), ("beta", 2.5)]


def test_vector_postgis_writer_fails_with_extra_fields(
    processing_worker_session: "Session", test_table: None
) -> None:
    """Extra columns in the GeoDataFrame that don't exist in the table raise an error."""
    gdf = geopandas.GeoDataFrame(
        {"name": ["alpha"], "score": [1.5], "unknown_column": ["x"]},
        geometry=[Point(385000, 6672000)],
        crs="EPSG:3067",
    )
    gdf.rename_geometry("geom", inplace=True)
    stage = VectorPostgisWriter(_SCHEMA, _TABLE, processing_worker_session)

    with pytest.raises(psycopg.errors.UndefinedColumn):
        stage.process(core.VectorDataset(geodataframe=gdf))


def test_vector_postgis_writer_fails_with_missing_required_fields(
    processing_worker_session: "Session", test_table: None
) -> None:
    """Missing a NOT NULL column causes a NotNullViolation."""
    gdf = geopandas.GeoDataFrame(
        {"score": [1.5]},
        geometry=[Point(385000, 6672000)],
        crs="EPSG:3067",
    )
    gdf.rename_geometry("geom", inplace=True)
    stage = VectorPostgisWriter(_SCHEMA, _TABLE, processing_worker_session)

    with pytest.raises(psycopg.errors.NotNullViolation):
        stage.process(core.VectorDataset(geodataframe=gdf))
