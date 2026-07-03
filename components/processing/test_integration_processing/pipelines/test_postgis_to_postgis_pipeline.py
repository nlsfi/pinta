# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import tempfile
import typing
from pathlib import Path

import numpy as np
import rasterio
import sqlalchemy as sa
from pinta_db.job_db.models import user
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from pinta_db_utils.postgis import raster
from pinta_test_utils import pinta_utils

from pinta_processing import pipelines, reader, writer

if typing.TYPE_CHECKING:
    from sqlmodel import Session

_SOURCE_SCHEMA, _SOURCE_TABLE = model_utils.schema_and_table(dem.Dem)
_TARGET_SCHEMA, _TARGET_TABLE = model_utils.schema_and_table(user.DemPreview)


def test_postgis_to_postgis_copies_source_raster_to_target(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
) -> None:
    """The pipeline copies the source raster into the (empty) target table."""
    bounds = _populate_source(admin_primary_session)
    _init_target(processing_worker_session)

    pipelines.postgis_to_postgis(
        from_session=session,
        from_schema=_SOURCE_SCHEMA,
        from_table=_SOURCE_TABLE,
        to_session=processing_worker_session,
        to_schema=_TARGET_SCHEMA,
        to_table=_TARGET_TABLE,
        tile_wkt=_bounds_to_wkt(*bounds),
    ).execute()

    source_array = _read_back(session, _SOURCE_SCHEMA, _SOURCE_TABLE)
    target_array = _read_back(processing_worker_session, _TARGET_SCHEMA, _TARGET_TABLE)
    assert target_array is not None
    assert source_array is not None
    assert target_array.shape == source_array.shape
    assert np.array_equal(target_array, source_array)


def test_postgis_to_postgis_writes_overview_tables(
    admin_primary_session: "Session",
    session: "Session",
    processing_worker_session: "Session",
) -> None:
    """The pipeline also fills the target overview tables, downsampled per level."""
    bounds = _populate_source(admin_primary_session)
    _init_target(processing_worker_session)

    pipelines.postgis_to_postgis(
        from_session=session,
        from_schema=_SOURCE_SCHEMA,
        from_table=_SOURCE_TABLE,
        to_session=processing_worker_session,
        to_schema=_TARGET_SCHEMA,
        to_table=_TARGET_TABLE,
        tile_wkt=_bounds_to_wkt(*bounds),
    ).execute()

    for level in raster.DEFAULT_OVERVIEW_LEVELS:
        overview_table = raster.OVERVIEW_TABLE_NAME.format(
            level=level, table_name=_TARGET_TABLE
        )
        count = processing_worker_session.exec(  # type: ignore[call-overload]
            sa.text(f"SELECT COUNT(*) FROM {_TARGET_SCHEMA}.{overview_table}")
        ).first()[0]
        assert count > 0, f"Expected overview level {level} to have rows"


def _populate_source(
    admin_primary_session: "Session",
) -> tuple[float, float, float, float]:
    """Write the test DEM into the source table and return its bounds."""
    raster.initialize_raster_table(admin_primary_session, _SOURCE_SCHEMA, _SOURCE_TABLE)
    file_path = pinta_utils.get_test_data_path("processing/dem.tif")

    (
        reader.RasterioReader(str(file_path))
        | writer.RasterPostgisWriter(
            _SOURCE_SCHEMA, _SOURCE_TABLE, admin_primary_session
        )
    ).execute()

    with rasterio.open(str(file_path)) as src:
        return (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)


def _init_target(processing_worker_session: "Session") -> None:
    """Ensure the target raster table and its overview tables exist and are empty."""
    raster.initialize_raster_table(
        processing_worker_session, _TARGET_SCHEMA, _TARGET_TABLE, staging_tables=0
    )
    raster.initialize_overview_tables(
        processing_worker_session, _TARGET_SCHEMA, _TARGET_TABLE, staging_tables=0
    )


def _read_back(session: "Session", schema: str, table: str) -> np.ndarray | None:
    """Merge all tiles of a raster table back into a single array via GDAL."""
    raster_binary = session.exec(  # type: ignore[call-overload]
        sa.text(
            f"SELECT ST_AsGDALRaster(ST_Union(rast), 'GTiff') FROM {schema}.{table}"
        )
    ).first()[0]
    if raster_binary is None:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "target.tif"
        output_path.write_bytes(raster_binary)
        with rasterio.open(str(output_path)) as src:
            return src.read(1)


def _bounds_to_wkt(left: float, bottom: float, right: float, top: float) -> str:
    return (
        "POLYGON(("
        f"{left} {bottom}, "
        f"{right} {bottom}, "
        f"{right} {top}, "
        f"{left} {top}, "
        f"{left} {bottom}"
        "))"
    )
