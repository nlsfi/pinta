# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
from typing import TYPE_CHECKING

import rasterio

from pinta_processing import core

if TYPE_CHECKING:
    from pathlib import Path


class RasterioReader(core.Stage):
    """Read raster files using rasterio.

    Reads the first band and extracts georeferencing information
    (transform, CRS, nodata values) from the file metadata.
    """

    def __init__(self, path: "str | Path") -> None:
        """Initialize RasterioReader."""
        self.path = path

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:  # noqa: ARG002
        """Read raster file and return RasterDataset."""
        with rasterio.open(self.path) as src:
            return core.RasterDataset.from_rasterio(src)
