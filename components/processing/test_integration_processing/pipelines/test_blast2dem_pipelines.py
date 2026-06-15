# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from pathlib import Path

import pytest
import rasterio
import sqlalchemy as sa
from pinta_common import env
from pinta_db_utils.postgis import raster
from pinta_test_utils import pinta_utils

from pinta_processing import pipelines
from pinta_processing.reader.lastools import Blast2DemReader

if typing.TYPE_CHECKING:
    from sqlmodel import Session

_LAZ_FILE = Path("point_clouds/2025/production_area_1/N5122B4_1.laz")
_STEP = 2
_KEEP_CLASS = [2]


@pytest.fixture(autouse=True)
def _ensure_lastools_is_available(lastools_in_path: None) -> None:
    pass


@pytest.fixture(autouse=True)
def set_blast2dem_executable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Blast2DemReader, "executable", "las2dem_new64")


def test_blast2dem_to_geotiff(
    tmp_path: Path,
) -> None:
    input_path = pinta_utils.get_test_data_path(_LAZ_FILE)
    output_path = str(tmp_path / "output.tif")

    pipeline = pipelines.blast2dem_to_geotiff(
        input_path=input_path,
        output_path=output_path,
        step=_STEP,
        keep_class=_KEEP_CLASS,
    )
    pipeline.execute()

    with rasterio.open(output_path) as src:
        assert src.crs.to_epsg() == int(env.SRID)
        assert src.count == 1
        assert src.width > 0
        assert src.height > 0
        assert src.dtypes[0] == "float32"
        assert src.nodata is not None
        assert src.transform != rasterio.transform.IDENTITY


def test_blast2dem_to_postgis(
    processing_worker_session: "Session", session: "Session"
) -> None:
    table_name = "dem"
    schema = "reference"
    staging_tables = 2

    raster.initialize_raster_table(
        processing_worker_session, schema, table_name, staging_tables
    )
    raster.initialize_overview_tables(
        processing_worker_session, schema, table_name, staging_tables
    )

    input_path = pinta_utils.get_test_data_path(_LAZ_FILE)

    pipeline = pipelines.blast2dem_to_postgis(
        primary_session=session,
        job_session=processing_worker_session,
        input_path=input_path,
        schema=schema,
        table_name=table_name,
        step=_STEP,
        keep_class=_KEEP_CLASS,
    )
    pipeline.execute()

    raster.merge_staging_tables(
        schema, table_name, staging_tables, processing_worker_session
    )

    main_count = processing_worker_session.exec(  # type: ignore[call-overload]
        sa.text(f"SELECT COUNT(*) FROM {schema}.{table_name}")
    ).first()[0]
    assert main_count > 0, f"Expected rows in {schema}.{table_name}, got 0"
