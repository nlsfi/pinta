# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import logging
import pathlib
import tempfile
import zipfile
from typing import Any

import rasterio
import sqlalchemy as sa
import sqlmodel
from rasterio.io import MemoryFile

from pinta_processing import core

LOGGER = logging.getLogger(__name__)


class RasterioReader(core.Stage):
    """Read raster files using rasterio.

    Reads the first band and extracts georeferencing information
    (transform, CRS, nodata values) from the file metadata.
    """

    def __init__(self, path: str | pathlib.Path, crs: str | None = None) -> None:
        """Initialize RasterioReader."""
        self.path = pathlib.Path(path)
        self.crs = crs

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:  # noqa: ARG002
        """Read raster file and return RasterDataset."""
        if self.path.suffix.lower() == ".zip":
            self.path = self._extract_from_zip(self.path)

        return self._rasterio_to_dataset()

    def _extract_from_zip(self, zip_path: pathlib.Path) -> pathlib.Path:
        """Extract raster file from zip archive and return path.

        Raises ValueError if zip contains 0 or multiple files.
        """
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            file_list = zip_file.namelist()
            # Filter out directories
            file_list = [f for f in file_list if not f.endswith("/")]

            if len(file_list) == 0:
                msg = "No files found in zip archive"
                raise ValueError(msg)
            if len(file_list) > 1:
                msg = f"Zip archive contains {len(file_list)} files, expected exactly 1"
                raise ValueError(msg)

            # Create temporary directory and extract
            self._temp_dir = tempfile.TemporaryDirectory()
            zip_file.extractall(self._temp_dir.name)

        return pathlib.Path(self._temp_dir.name) / file_list[0]

    def _rasterio_to_dataset(self) -> core.RasterDataset:
        """Convert rasterio dataset to RasterDataset."""
        with rasterio.open(self.path) as src:
            dataset = core.RasterDataset.from_rasterio(src)

            if (
                self.crs is not None
                and dataset.crs is not None
                and dataset.crs != self.crs
                and f'["EPSG","{self.crs.split(":")[1]}"]' not in dataset.crs
            ):
                msg = (
                    f"CRS mismatch: raster file has CRS {dataset.crs} "
                    f"but {self.crs} was specified. Reprojection is not supported."
                )
                raise NotImplementedError(msg)

            if self.crs is not None:
                dataset = core.RasterDataset(
                    array=dataset.array,
                    transform=dataset.transform,
                    crs=self.crs,
                    nodata=dataset.nodata,
                )
            if dataset.crs is None:
                LOGGER.warning(
                    "Raster file %s has no CRS information and no CRS "
                    "manually specified",
                    self.path,
                )
            return dataset


class PostgisReader(core.Stage):
    """Read and clip raster data from a PostGIS raster table."""

    def __init__(
        self,
        schema: str,
        table_name: str,
        session: sqlmodel.Session,
        wkt: str,
    ) -> None:
        super().__init__()
        self.schema = schema
        self.table_name = table_name
        self.session = session
        self.wkt = wkt

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:  # noqa: ARG002
        """Read raster tiles from PostGIS, clip them by WKT, and return a dataset."""
        result = self.session.exec(self._clip_query(), params={"wkt": self.wkt})
        row = result.first()
        if row is None or row[0] is None:
            message = (
                f"No raster data found in {self.schema}.{self.table_name} "
                "for the given clipping geometry"
            )
            raise ValueError(message)

        with MemoryFile(_to_bytes(row[0])) as memory_file, memory_file.open() as src:
            return core.RasterDataset.from_rasterio(src)

    def _clip_query(self) -> sa.Select[tuple[Any]]:
        table = sa.Table(
            self.table_name,
            sa.MetaData(),
            sa.Column("rast"),
            schema=self.schema,
        )

        srid = (
            sa.select(sa.func.ST_SRID(table.c.rast))
            .where(table.c.rast.is_not(None))
            .limit(1)
            .scalar_subquery()
        )
        clip_geom = sa.func.ST_GeomFromText(sa.bindparam("wkt"), srid)
        source = (
            sa.select(sa.func.ST_Union(table.c.rast).label("rast"))
            .where(sa.func.ST_Intersects(table.c.rast, clip_geom))
            .cte("source")
        )

        return sa.select(
            sa.func.ST_AsGDALRaster(
                sa.func.ST_Clip(source.c.rast, clip_geom, sa.true()),
                "GTiff",
            ).label("geotiff_data")
        ).where(source.c.rast.is_not(None))


def _to_bytes(value: bytes | memoryview) -> bytes:
    """Convert DB binary values to bytes."""
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)
