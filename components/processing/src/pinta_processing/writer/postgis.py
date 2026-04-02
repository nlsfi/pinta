# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""PostGIS writer for RasterDataset.

See more details from wkb raster format rfc docs:
https://trac.osgeo.org/postgis/wiki/WKTRaster/RFC/RFC2_V0WKBFormat
"""

import hashlib
import struct
from dataclasses import dataclass

import sqlmodel
from rasterio.transform import Affine

from pinta_processing import core, exceptions

DEFAULT_TILE_SIZE = 256


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


class PostgisWriter(core.Stage):
    """Write raster data to PostGIS table using COPY FROM stdin."""

    def __init__(
        self,
        schema: str,
        table_name: str,
        session: sqlmodel.Session,
        staging_tables: int = 0,
    ) -> None:
        super().__init__()
        self.schema = schema
        self.table_name = table_name
        self.session = session
        self.staging_tables = staging_tables

    def process(self, data: core.RasterDataset | None) -> None:
        """Write raster data to PostGIS table."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=PostgisWriter.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        if self.staging_tables == 0:
            return self._write_to_postgis(data, self.table_name)

        partition = self._resolve_partition(data)
        return self._write_to_postgis(data, f"{self.table_name}_p{partition}")

    def _write_to_postgis(self, data: core.RasterDataset, table_name: str) -> None:
        """Tile and write RasterDataset to PostGIS table."""
        # Get the raw psycopg2 connection for batch operations
        raw_connection = self.session.connection().connection
        copy_sql = f"COPY {self.schema}.{table_name} (rast) FROM STDIN"

        with raw_connection.cursor() as cursor, cursor.copy(copy_sql) as copy:
            for tile_data in self._generate_tiles(data):
                raster_bytes = self._raster_dataset_to_postgis_bytes(tile_data)
                copy.write(raster_bytes.hex() + "\n")

        raw_connection.commit()

    def _generate_tiles(
        self, data: core.RasterDataset, tile_size: int = DEFAULT_TILE_SIZE
    ) -> list[core.RasterDataset]:
        """Generate tiles as RasterDataset objects.

        Each tile is a RasterDataset with the proper array slice, transform,
        CRS, and nodata value for writing to PostGIS. Last tile might be smaller if
        dimensions are not divisible by tile_size.
        """
        tiles = []
        height, width = data.array.shape[:2]

        for row in range(0, height, tile_size):
            for col in range(0, width, tile_size):
                # Calculate tile dimensions (last tiles may be smaller)
                tile_height = min(tile_size, height - row)
                tile_width = min(tile_size, width - col)

                # Extract tile array
                tile_array = data.array[
                    row : row + tile_height,
                    col : col + tile_width,
                ]

                # Calculate the transform for this tile's upper-left corner
                tile_transform = data.transform * Affine.translation(col, row)

                # Create RasterDataset for this tile
                tile_data = core.RasterDataset(
                    array=tile_array,
                    transform=tile_transform,
                    crs=data.crs,
                    nodata=data.nodata,
                )

                tiles.append(tile_data)

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
