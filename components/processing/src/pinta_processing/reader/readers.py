# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import dataclasses
import logging
import math
import pathlib
import tempfile
import zipfile
from typing import Any

import affine
import numpy as np
import rasterio
import sqlalchemy as sa
import sqlmodel
from pinta_common import settings
from rasterio.io import MemoryFile
from shapely import wkt as shapely_wkt

from pinta_processing import core

LOGGER = logging.getLogger(__name__)

# Rows buffered per fetch when streaming clipped tiles from the database.
_STREAM_ROW_BUFFER = 8

# Tolerance (in pixels) when snapping clip bounds to the tile pixel lattice.
_SNAP_PIXEL_TOLERANCE = 1e-6


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


@dataclasses.dataclass(frozen=True)
class ClippedGridMetadata:
    """Pixel grid metadata of the tiles intersecting a clip geometry."""

    bounds: tuple[float, float, float, float]  # (left, bottom, right, top)
    scale_x: float
    scale_y: float  # negative for north-up rasters
    nodata: float | None
    srid: int


class PostgisReader(core.Stage):
    """Read and clip raster data from a PostGIS raster table.

    The intersecting tiles are clipped and streamed out of the database one row
    at a time and mosaicked client-side. The database backend never holds more
    than a single tile in memory, which keeps arbitrarily large clip geometries
    clear of backend out-of-memory failures.
    """

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
        grid = self._read_raster_metadata()
        transform, height, width = self._build_mosaic_grid(grid)
        if height <= 0 or width <= 0:
            message = (
                f"No raster data found in {self.schema}.{self.table_name} "
                "for the given clipping geometry"
            )
            raise ValueError(message)

        mosaic = np.full((height, width), grid.nodata, dtype=np.float32)

        crs: str | None = None
        result = self.session.exec(self._tile_query(), params={"wkt": self.wkt})
        for row in result:
            if row[0] is None:
                continue
            with (
                MemoryFile(_to_bytes(row[0])) as memory_file,
                memory_file.open() as src,
            ):
                if crs is None and src.crs is not None:
                    crs = src.crs.to_string()
                _place_tile(mosaic, transform, src.read(1), src.transform, grid.nodata)

        return core.RasterDataset(
            array=mosaic,
            transform=transform,
            crs=crs if crs is not None else f"EPSG:{grid.srid}",
            nodata=grid.nodata,
        )

    def _read_raster_metadata(self) -> ClippedGridMetadata:
        """Fetch the extent and pixel grid of the tiles intersecting the WKT.

        The scale, nodata and SRID aggregates are arbitrary picks: the raster
        constraints guarantee every tile in the table shares them.
        """
        table = self.table
        tiles = (
            sa.select(
                sa.func.ST_Extent(sa.func.ST_Envelope(table.c.rast)).label("extent"),
                sa.func.min(sa.func.ST_ScaleX(table.c.rast)).label("scale_x"),
                sa.func.max(sa.func.ST_ScaleY(table.c.rast)).label("scale_y"),
                sa.func.min(sa.func.ST_BandNoDataValue(table.c.rast, 1)).label(
                    "nodata"
                ),
                sa.func.min(sa.func.ST_SRID(table.c.rast)).label("srid"),
            )
            .where(
                sa.func.ST_Intersects(
                    table.c.rast,
                    sa.func.ST_GeomFromText(
                        sa.bindparam("wkt"), int(settings.Settings.DB_SRID)
                    ),
                )
            )
            .subquery("tiles")
        )
        query = sa.select(
            sa.func.ST_XMin(tiles.c.extent),
            sa.func.ST_YMin(tiles.c.extent),
            sa.func.ST_XMax(tiles.c.extent),
            sa.func.ST_YMax(tiles.c.extent),
            tiles.c.scale_x,
            tiles.c.scale_y,
            tiles.c.nodata,
            tiles.c.srid,
        )

        row = self.session.exec(query, params={"wkt": self.wkt}).first()
        if row is None or row[0] is None:
            message = (
                f"No raster data found in {self.schema}.{self.table_name} "
                "for the given clipping geometry"
            )
            raise ValueError(message)
        left, bottom, right, top, scale_x, scale_y, nodata, srid = row
        return ClippedGridMetadata(
            bounds=(left, bottom, right, top),
            scale_x=scale_x,
            scale_y=scale_y,
            nodata=nodata,
            srid=int(srid),
        )

    def _build_mosaic_grid(
        self, grid: ClippedGridMetadata
    ) -> tuple[affine.Affine, int, int]:
        """Clip bounds intersected with the tiles and snapped to their lattice."""
        clip_left, clip_bottom, clip_right, clip_top = shapely_wkt.loads(
            self.wkt
        ).bounds
        tiles_left, tiles_bottom, tiles_right, tiles_top = grid.bounds
        pixel_width = grid.scale_x
        pixel_height = -grid.scale_y

        left = _snap(max(clip_left, tiles_left), tiles_left, pixel_width, up=False)
        right = _snap(min(clip_right, tiles_right), tiles_left, pixel_width, up=True)
        bottom = _snap(
            max(clip_bottom, tiles_bottom), tiles_top, pixel_height, up=False
        )
        top = _snap(min(clip_top, tiles_top), tiles_top, pixel_height, up=True)

        transform = affine.Affine(grid.scale_x, 0.0, left, 0.0, grid.scale_y, top)
        width = round((right - left) / pixel_width)
        height = round((top - bottom) / pixel_height)
        return transform, height, width

    @property
    def table(self) -> sa.Table:
        """Return a SQLAlchemy Table object for the raster table."""
        return sa.Table(
            self.table_name,
            sa.MetaData(),
            sa.Column("rast"),
            schema=self.schema,
        )

    def _tile_query(self) -> sa.Select[tuple[Any]]:
        """Stream each intersecting tile clipped to the geometry as a GeoTIFF.

        ST_Clip runs in a LATERAL subquery so its result can be filtered
        without being recomputed per reference and without materializing the
        whole clipped set. Tiles that only touch the geometry clip to an empty
        raster and are dropped, ST_AsGDALRaster would fail on them.
        """
        table = self.table
        clipped = (
            sa.select(
                sa.func.ST_Clip(
                    table.c.rast,
                    sa.func.ST_GeomFromText(
                        sa.bindparam("wkt"), int(settings.Settings.DB_SRID)
                    ),
                    sa.true(),
                ).label("rast")
            )
            .correlate(table)
            .lateral("clipped")
        )
        return (
            sa.select(sa.func.ST_AsGDALRaster(clipped.c.rast, "GTiff"))
            .select_from(sa.join(table, clipped, sa.true()))
            .where(
                sa.func.ST_Intersects(
                    table.c.rast,
                    sa.func.ST_GeomFromText(
                        sa.bindparam("wkt"), int(settings.Settings.DB_SRID)
                    ),
                )
            )
            .where(clipped.c.rast.is_not(None))
            .where(sa.func.ST_IsEmpty(clipped.c.rast).is_(sa.false()))
            .execution_options(stream_results=True, max_row_buffer=_STREAM_ROW_BUFFER)
        )


def _to_bytes(value: bytes | memoryview) -> bytes:
    """Convert DB binary values to bytes."""
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)


def _snap(value: float, origin: float, step: float, *, up: bool) -> float:
    """Snap value outward to the pixel lattice anchored at origin."""
    steps = (value - origin) / step
    index = (
        math.ceil(steps - _SNAP_PIXEL_TOLERANCE)
        if up
        else math.floor(steps + _SNAP_PIXEL_TOLERANCE)
    )
    return origin + index * step


def _place_tile(
    mosaic: np.ndarray,
    transform: affine.Affine,
    tile_array: np.ndarray,
    tile_transform: affine.Affine,
    nodata: float | None,
) -> None:
    """Copy the tile's valid pixels into the mosaic at its grid position."""
    if tile_array.size == 0:
        return
    col_offset = round((tile_transform.c - transform.c) / transform.a)
    row_offset = round((tile_transform.f - transform.f) / transform.e)
    height, width = tile_array.shape
    row_start = max(row_offset, 0)
    col_start = max(col_offset, 0)
    row_stop = min(row_offset + height, mosaic.shape[0])
    col_stop = min(col_offset + width, mosaic.shape[1])
    if row_start >= row_stop or col_start >= col_stop:
        return
    source = tile_array[
        row_start - row_offset : row_stop - row_offset,
        col_start - col_offset : col_stop - col_offset,
    ]
    target = mosaic[row_start:row_stop, col_start:col_stop]
    if nodata is None:
        target[:] = source
        return
    valid = ~np.isnan(source) if math.isnan(nodata) else source != nodata
    target[valid] = source[valid]
