# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from dataclasses import dataclass

import numpy as np
import pytest
import sqlalchemy as sa
from affine import Affine
from pinta_common import env
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from pinta_db_utils.postgis import raster
from sqlmodel import SQLModel, select

from pinta_processing import core, pipelines, writer
from pinta_processing.utils import tm35_map_sheet_utils

if typing.TYPE_CHECKING:
    from sqlmodel import Session

TILE = "N5122B4_1"
PIXEL_SIZE = 2
BASE_ELEVATION = 100.0
THRESHOLD = 0.2
STAGING_TABLES = 1

# Deltas placed safely either side of the threshold.
OVER = 0.6
UNDER = 0.1


@dataclass(frozen=True)
class DiffArea:
    """Square area where the reference surface differs from the DEM by `delta` m.

    `abs(delta) > threshold` ends up as a diff polygon, a smaller non-zero
    delta as a dior region. Areas must not touch (4-connectivity) so each stays
    a separate cluster.
    """

    col: int
    row: int
    size: int
    delta: float


def _build_surfaces(
    areas: list[DiffArea],
) -> tuple[core.RasterDataset, core.RasterDataset]:
    """Build aligned DEM and reference rasters covering the test tile."""
    minx, miny, maxx, maxy = tm35_map_sheet_utils.calculate_sheet_bounds_for_tile(TILE)
    width = (maxx - minx) // PIXEL_SIZE
    height = (maxy - miny) // PIXEL_SIZE
    transform = Affine.translation(minx, maxy) * Affine.scale(PIXEL_SIZE, -PIXEL_SIZE)

    dem_array = np.full((height, width), BASE_ELEVATION, dtype=np.float32)
    reference_array = dem_array.copy()
    for area in areas:
        reference_array[
            area.row : area.row + area.size, area.col : area.col + area.size
        ] += area.delta

    def dataset(array: np.ndarray) -> core.RasterDataset:
        return core.RasterDataset(
            array=array,
            transform=transform,
            crs=f"EPSG:{env.SRID}",
            nodata=env.DEM_NODATA,
        )

    return dataset(dem_array), dataset(reference_array)


def _init_raster_tables(session: "Session", model: type[SQLModel]) -> tuple[str, str]:
    schema, table = model_utils.schema_and_table(model)
    raster.initialize_raster_table(session, schema, table, STAGING_TABLES)
    raster.initialize_overview_tables(session, schema, table, STAGING_TABLES)
    return schema, table


def _merge_staging(session: "Session", schema: str, table: str) -> None:
    raster.merge_staging_tables(schema, table, STAGING_TABLES, session)
    for level in raster.DEFAULT_OVERVIEW_LEVELS:
        overview = raster.OVERVIEW_TABLE_NAME.format(level=level, table_name=table)
        raster.merge_staging_tables(
            schema, overview, STAGING_TABLES, session, overview_level=level
        )


def _write_raster(
    session: "Session", model: type[SQLModel], dataset: core.RasterDataset
) -> None:
    schema, table = _init_raster_tables(session, model)
    (
        pipelines._generate_overview_stages(schema, table, session, STAGING_TABLES)
        | writer.RasterPostgisWriter(schema, table, session, STAGING_TABLES)
    ).process(dataset)
    _merge_staging(session, schema, table)


def _populate(
    primary_session: "Session", job_session: "Session", areas: list[DiffArea]
) -> None:
    dem_dataset, reference_dataset = _build_surfaces(areas)
    _write_raster(primary_session, dem.Dem, dem_dataset)
    _write_raster(job_session, reference.Dem, reference_dataset)
    # Staging tables the diff pipeline writes its raster output into.
    _init_raster_tables(job_session, reference.Diff)
    _init_raster_tables(job_session, reference.DiffDior)
    job_session.commit()


def _dior_region_count(session: "Session") -> int:
    """Count distinct non-zero (sub-threshold) areas in the dior raster."""
    schema, table = model_utils.schema_and_table(reference.DiffDior)
    return session.exec(  # type: ignore[call-overload]
        sa.text(f"""
            WITH unioned AS (
                SELECT ST_Union(rast) AS rast FROM {schema}.{table}_p0
            )
            SELECT count(*)
            FROM (SELECT (ST_DumpAsPolygons(rast)).val AS val FROM unioned) regions
            WHERE val <> 0
        """)
    ).first()[0]


@pytest.mark.parametrize(
    ("areas", "expected_polygons", "expected_dior_regions"),
    [
        pytest.param([DiffArea(60, 60, 40, OVER)], 1, 0, id="single-over"),
        pytest.param(
            [
                DiffArea(60, 60, 40, OVER),
                DiffArea(300, 300, 40, OVER),
                DiffArea(60, 300, 40, UNDER),
                DiffArea(300, 60, 40, UNDER),
            ],
            2,
            2,
            id="two-over-two-under",
        ),
        pytest.param(
            [DiffArea(60, 60, 40, UNDER), DiffArea(300, 300, 40, UNDER)],
            0,
            2,
            id="two-under-only",
        ),
    ],
)
def test_calculate_diff_models(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
    areas: list[DiffArea],
    expected_polygons: int,
    expected_dior_regions: int,
) -> None:
    _populate(admin_primary_session, processing_worker_session, areas)
    wkt = tm35_map_sheet_utils.calculate_bounding_box_for_tile(TILE).wkt

    pipelines.calculate_diff_models(
        session,
        processing_worker_session,
        tile_wkt=wkt,
        staging_tables=STAGING_TABLES,
        threshold=THRESHOLD,
    ).execute()

    polygons = processing_worker_session.exec(select(reference.DiffPolygon)).all()

    assert len(polygons) == expected_polygons
    assert all(polygon.geom is not None for polygon in polygons)
    assert _dior_region_count(processing_worker_session) == expected_dior_regions
