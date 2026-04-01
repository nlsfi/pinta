# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from rasterio.enums import Resampling
from rasterio.io import MemoryFile

from pinta_processing import core, exceptions


class DownsampleOverview(core.Stage):
    """Downsample raster to a lower resolution overview using average resampling."""

    def __init__(self, factor: int = 2) -> None:
        self.factor = factor

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset | None:
        """Downsample raster by applying GDAL average resampling via MemoryFile."""
        if data is None:
            return None

        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=DownsampleOverview.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        factor = self.factor
        height, width = data.array.shape
        new_height, new_width = height // factor, width // factor

        profile = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": 1,
            "dtype": data.array.dtype,
            "crs": data.crs,
            "transform": data.transform,
            "nodata": data.nodata,
        }

        with MemoryFile() as memory_file:
            with memory_file.open(**profile) as dataset:
                dataset.write(data.array, 1)

            with memory_file.open() as dataset:
                downsampled = dataset.read(
                    1,
                    out_shape=(new_height, new_width),
                    resampling=Resampling.average,
                )

        new_transform = data.transform * data.transform.scale(
            width / new_width,
            height / new_height,
        )

        return core.RasterDataset(
            array=downsampled,
            transform=new_transform,
            crs=data.crs,
            nodata=data.nodata,
        )
