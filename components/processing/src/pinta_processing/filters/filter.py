# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from pinta_processing import core, exceptions


class RasterFilter(core.Stage):
    """Filter raster values using an element-wise predicate.

    Values for which the predicate returns false are replaced with nodata.
    Existing nodata values are preserved and excluded from predicate results.
    """

    def __init__(self, predicate: Callable[[NDArray], NDArray]) -> None:
        super().__init__()
        self.predicate = predicate

    def process(self, data: core.RasterDataset) -> core.RasterDataset:
        """Apply predicate to raster values and replace rejected cells with nodata."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterFilter.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        predicate_mask = np.asarray(self.predicate(data.array), dtype=bool)
        if predicate_mask.shape != data.array.shape:
            message = (
                "RasterFilter predicate must return a mask with the same shape "
                "as the input raster array"
            )
            raise ValueError(message)

        if data.nodata is None:
            arr = data.array.astype(float, copy=True)
            nodata = np.nan
            valid_mask = np.ones(data.array.shape, dtype=bool)
        else:
            arr = data.array.copy()
            nodata = data.nodata
            valid_mask = arr != data.nodata

        arr[valid_mask & ~predicate_mask] = nodata

        return core.RasterDataset(
            array=arr, transform=data.transform, crs=data.crs, nodata=nodata
        )
