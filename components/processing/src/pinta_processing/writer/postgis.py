# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS writer for RasterDataset.

See more details from wkb raster format rfc docs:
https://trac.osgeo.org/postgis/wiki/WKTRaster/RFC/RFC2_V0WKBFormat
"""

import hashlib
import logging
import math
import struct
from dataclasses import dataclass
from typing import Literal

import numpy as np
import sqlmodel
from affine import Affine
from pinta_common import Settings
from rasterio.windows import Window, from_bounds

from pinta_processing import core, exceptions

LOGGER = logging.getLogger(__name__)

WriterMode = Literal["insert", "update"]

# Output pixel type for merged tiles, matching the float32 DEM band.
_MERGE_PIXEL_TYPE = "32BF"

# When updating existing tiles, TEMP table holding incoming tiles before they are
# merged into the target table.
_UPDATE_STAGING_TABLE = "_pinta_raster_update_staging"


@dataclass
class DataTypeConfig:
    """Configuration for PostGIS data types."""

    pg_pixtype: int
    struct_key: str

    @staticmethod
    def from_numpy_dtype(numpy_dtype: str) -> "DataTypeConfig":
        """Get DataTypeConfig from numpy dtype string."""
        try:
            return {
                # https://github.com/ahinz/postgis/blob/594053704afc98250e74af31100ad969010c32b5/raster/rt_core/rt_api.h#L169
                # https://docs.python.org/3/library/struct.html#format-characters
                "float32": DataTypeConfig(10, "f"),
            }[numpy_dtype]
        except KeyError:
            raise NotImplementedError(
                f"data type {numpy_dtype} not implemented"
            ) from None


class RasterPostgisWriter(core.Stage):
    """Write raster data to PostGIS table using COPY FROM stdin."""

    def __init__(  # noqa: PLR0913
        self,
        schema: str,
        table_name: str,
        session: sqlmodel.Session,
        staging_tables: int = 0,
        tile_size: int | None = None,
        mode: WriterMode = "insert",
    ) -> None:
        super().__init__()
        if mode == "update" and staging_tables != 0:
            msg = "update mode requires staging_tables=0"
            raise ValueError(msg)
        self.schema = schema
        self.table_name = table_name
        self.session = session
        self.staging_tables = staging_tables
        self.mode = mode
        self.tile_size = (
            tile_size if tile_size is not None else Settings.DB_DEFAULT_TILE_SIZE
        )

    def process(self, data: core.RasterDataset | None) -> None:
        """Write raster data to PostGIS table."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterPostgisWriter.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        if data.crs is None:
            msg = "CRS is required for writing to PostGIS. "
            raise ValueError(msg)

        if self.mode == "update":
            return self._update_to_postgis(data)
        if self.staging_tables == 0:
            return self._write_to_postgis(data, self.table_name)

        partition = self._resolve_partition(data)
        return self._write_to_postgis(data, f"{self.table_name}_p{partition}")

    def _write_to_postgis(self, data: core.RasterDataset, table_name: str) -> None:
        """Tile and write RasterDataset to PostGIS table."""
        # Get the raw psycopg2 connection for batch operations
        raw_connection = self.session.connection().connection
        copy_sql = f"COPY {self.schema}.{table_name} (rast) FROM STDIN"
        LOGGER.info("Writing data to table %s.%s using COPY", self.schema, table_name)
        with raw_connection.cursor() as cursor, cursor.copy(copy_sql) as copy:
            for tile_data in self._generate_tiles(data):
                raster_bytes = self._raster_dataset_to_postgis_bytes(tile_data)
                copy.write(raster_bytes.hex() + "\n")

        raw_connection.commit()

    def _update_to_postgis(self, data: core.RasterDataset) -> None:
        """Merge raster tiles into an existing PostGIS table.

        Incoming pixels overwrite the target, target pixels are
        kept where the incoming tile is nodata. Tiles with no matching row yet
        are inserted.
        """
        tiles = [tile for tile in self._generate_tiles(data) if _tile_has_data(tile)]
        if not tiles:
            LOGGER.info(
                "No data to merge into table %s.%s", self.schema, self.table_name
            )
            return

        raw_connection = self.session.connection().connection
        nodata_value = data.nodata if data.nodata is not None else 0.0
        LOGGER.info("Merging data into table %s.%s", self.schema, self.table_name)
        try:
            with raw_connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE TEMP TABLE {_UPDATE_STAGING_TABLE} "
                    "(rast raster) ON COMMIT DROP"
                )
                copy_sql = f"COPY {_UPDATE_STAGING_TABLE} (rast) FROM STDIN"
                with cursor.copy(copy_sql) as copy:
                    for tile in tiles:
                        raster_bytes = self._raster_dataset_to_postgis_bytes(tile)
                        copy.write(raster_bytes.hex() + "\n")

                cursor.execute(self._merge_update_sql(), (nodata_value, nodata_value))
                cursor.execute(self._merge_insert_sql())

            raw_connection.commit()
        except Exception:
            raw_connection.rollback()
            raise

    def _merge_update_sql(self) -> str:
        """SQL merging staged tiles into existing rows via ST_MapAlgebra.

        Matches rows by extent. Takes two nodata
        parameters: the both-nodata fill value and the merged band's nodata.
        """
        # Schema/table come from trusted model metadata, not user input.
        target = f"{self.schema}.{self.table_name}"
        return f"""
            UPDATE {target} AS target
            SET rast = ST_SetBandNoDataValue(
                ST_MapAlgebra(
                    target.rast, staging.rast,
                    '[rast2]',              -- both valid: incoming wins
                    '{_MERGE_PIXEL_TYPE}',  -- output pixel type
                    'FIRST',                -- keep target extent
                    '[rast2]',              -- target nodata: use incoming
                    '[rast1]',              -- incoming nodata: keep target
                    %s                      -- both nodata: fill value
                ),
                %s
            )
            FROM {_UPDATE_STAGING_TABLE} AS staging
            WHERE target.rast::geometry = staging.rast::geometry
        """  # noqa: S608

    def _merge_insert_sql(self) -> str:
        # Schema/table come from trusted model metadata, not user input.
        target = f"{self.schema}.{self.table_name}"
        return f"""
            INSERT INTO {target} (rast)
            SELECT staging.rast
            FROM {_UPDATE_STAGING_TABLE} AS staging
            WHERE NOT EXISTS (
                SELECT 1 FROM {target} AS target
                WHERE target.rast::geometry = staging.rast::geometry
            )
        """  # noqa: S608

    def _generate_tiles(
        self,
        data: core.RasterDataset,
        x0: float = 500000,
        y0: float = 6570000,
    ) -> list[core.RasterDataset]:
        """Generate tiles from a RasterDataset.

        Generate tiles covering input data on a global grid to ensure regular
        blocking. Initialize tiles with nodata and fill tiles accordingly with
        input data.
        """
        tiles = []

        transform = data.transform
        pixel_width = transform.a
        pixel_height = -transform.e

        tile_width = self.tile_size * pixel_width
        tile_height = self.tile_size * pixel_height

        height, width = data.array.shape[:2]

        if height == 0 or width == 0:
            return []

        nodata_value = data.nodata if data.nodata is not None else 0.0

        # Raster bounds
        xmin, ymax = transform * (0, 0)
        xmax, ymin = transform * (width, height)

        # Snap to global grid
        grid_xmin = x0 + math.floor((xmin - x0) / tile_width) * tile_width
        grid_xmax = x0 + math.ceil((xmax - x0) / tile_width) * tile_width

        grid_ymax = y0 + math.ceil((ymax - y0) / tile_height) * tile_height
        grid_ymin = y0 + math.floor((ymin - y0) / tile_height) * tile_height

        full_window = Window(0, 0, width, height)

        y = grid_ymax
        while y > grid_ymin:
            x = grid_xmin
            while x < grid_xmax:
                tile_bounds = (x, y - tile_height, x + tile_width, y)

                # Convert bounds to pixel window
                win = from_bounds(*tile_bounds, transform=transform)

                # Stabilize floating precision
                win = win.round_offsets().round_lengths()

                # Intersect with raster extent
                src_win = win.intersection(full_window)

                # Create empty tile
                tile_array = np.full(
                    (self.tile_size, self.tile_size),
                    nodata_value,
                    dtype=data.array.dtype,
                )

                if src_win.width > 0 and src_win.height > 0:
                    src = data.array[
                        int(src_win.row_off) : int(src_win.row_off + src_win.height),
                        int(src_win.col_off) : int(src_win.col_off + src_win.width),
                    ]

                    # Compute destination window inside tile
                    dst_row_off = int(src_win.row_off - win.row_off)
                    dst_col_off = int(src_win.col_off - win.col_off)

                    h, w = src.shape

                    tile_array[
                        dst_row_off : dst_row_off + h,
                        dst_col_off : dst_col_off + w,
                    ] = src

                # Compute tile transform
                tile_transform = Affine.translation(x, y) * Affine.scale(
                    pixel_width, -pixel_height
                )

                tiles.append(
                    core.RasterDataset(
                        array=tile_array,
                        transform=tile_transform,
                        crs=data.crs,
                        nodata=data.nodata,
                    )
                )

                x += tile_width
            y -= tile_height

        return tiles

    def _raster_dataset_to_postgis_bytes(self, data: core.RasterDataset) -> bytes:
        """Convert RasterDataset to PostGIS raster WKB binary format."""
        epsg_code = 0
        if data.crs and ":" in data.crs:
            epsg_code = int(data.crs.split(":")[-1])

        height, width = data.array.shape[:2]

        # Build WKB header
        header = [
            ("B", 1),  # 1: little endian (NDR)
            ("H", 0),  # format version
            ("H", 1),  # number of bands (assuming single band)
            ("d", data.transform.a),  # pixel width
            ("d", data.transform.e),  # pixel height
            ("d", data.transform.c),  # upper-left X
            ("d", data.transform.f),  # upper-left Y
            ("d", data.transform.b),  # rotation X
            ("d", data.transform.d),  # rotation Y
            ("i", epsg_code),  # SRID
            ("H", width),  # width
            ("H", height),  # height
        ]

        header_format = "<" + "".join(struct_key for struct_key, _ in header)
        result = struct.pack(header_format, *(val for _, val in header))

        # Get dtype string for band
        dtype_str = str(data.array.dtype)

        # Build band header with metadata
        datatype_config = DataTypeConfig.from_numpy_dtype(dtype_str)
        nodata_value = data.nodata if data.nodata is not None else 0.0

        band_header_bits = _bits_to_int(
            (0, 1),  # is-offline
            (1, 1),  # has-nodata
            (0, 1),  # is-nodata
            (0, 1),  # reserved
            (datatype_config.pg_pixtype, 4),  # pixtype
        )

        band_header = [
            ("B", band_header_bits),
            (datatype_config.struct_key, nodata_value),
        ]

        band_header_format = "<" + "".join(struct_key for struct_key, _ in band_header)
        result += struct.pack(band_header_format, *(val for _, val in band_header))

        # Add band data in row-major order, little-endian
        result += data.array.view(data.array.dtype.newbyteorder("<")).tobytes()

        return result

    def _resolve_partition(self, data: core.RasterDataset) -> int:
        """Determine which staging table to write to based on tile bbox."""
        # Calculate bbox from array shape and transform
        height, width = data.array.shape[:2]

        # Get bounds: (left, bottom, right, top)
        left, top = data.transform.c, data.transform.f
        right = left + width * data.transform.a
        bottom = top + height * data.transform.e

        bbox = (left, bottom, right, top)

        # Hash the bbox and take modulo by staging_tables
        bbox_str = ",".join(str(coordinate) for coordinate in bbox)
        bbox_hash = hashlib.sha256(bbox_str.encode()).hexdigest()
        return int(bbox_hash, 16) % self.staging_tables


def _bits_to_int(*bits: tuple[int, int]) -> int:
    """Convert bits to integer."""
    return int("".join(f"{value:0{size}b}" for value, size in bits), 2)


def _tile_has_data(tile: core.RasterDataset) -> bool:
    """Return True if the tile has at least one non-nodata pixel."""
    nodata = tile.nodata
    if nodata is None:
        return True
    if isinstance(nodata, float) and math.isnan(nodata):
        return bool(np.any(~np.isnan(tile.array)))
    return bool(np.any(tile.array != nodata))


class VectorPostgisWriter(core.Stage):
    """Write vector data to PostGIS table."""

    def __init__(
        self,
        schema: str,
        table_name: str,
        session: sqlmodel.Session,
    ) -> None:
        super().__init__()
        self.schema = schema
        self.table_name = table_name
        self.session = session

    def process(self, data: core.StageReturnType) -> None:
        """Write vector data to PostGIS table."""
        if not isinstance(data, core.VectorDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=VectorPostgisWriter.__name__,
                expected_type=core.VectorDataset.__name__,
                received_type=type(data).__name__,
            )
        self._write_to_postgis(data)

    def _write_to_postgis(self, data: core.VectorDataset) -> None:
        con = self.session.connection()
        LOGGER.info("Writing vector data to table %s.%s", self.schema, self.table_name)
        data.geodataframe.to_postgis(
            self.table_name,
            con,
            schema=self.schema,
            if_exists="append",
            index=False,
        )
