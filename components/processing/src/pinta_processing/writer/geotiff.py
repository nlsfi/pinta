# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
import rasterio

from pinta_processing import core, exceptions


class GeotiffWriter(core.Stage):
    """Write a RasterDataset to a GeoTIFF file."""

    def __init__(self, path: str, dtype: np.typing.DTypeLike | None = None) -> None:
        self.path = path
        self.dtype = dtype

    def process(self, raster: core.RasterDataset) -> None:
        """Write the RasterDataset to a GeoTIFF file."""
        if not isinstance(raster, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=GeotiffWriter.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(raster).__name__,
            )

        array = raster.array
        dtype = self.dtype or array.dtype
        height, width = array.shape

        with rasterio.open(
            self.path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=dtype,
            crs=raster.crs,
            transform=raster.transform,
            nodata=raster.nodata,
        ) as dst:
            dst.write(array.astype(dtype), 1)
