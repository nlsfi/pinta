# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np

from pinta_processing import core, exceptions


class RoundValues(core.Stage):
    """Round raster values to a specified precision."""

    def __init__(self, precision: int) -> None:
        super().__init__()
        self.precision = precision

    def process(self, data: core.RasterDataset) -> core.RasterDataset:
        """Round raster values to the specified precision."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=RoundValues.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )
        arr = data.array.copy()

        if data.nodata is not None:
            mask = arr != data.nodata
            arr[mask] = np.round(arr[mask], self.precision)
        else:
            arr = np.round(arr, self.precision)

        return core.RasterDataset(
            array=arr, transform=data.transform, crs=data.crs, nodata=data.nodata
        )
