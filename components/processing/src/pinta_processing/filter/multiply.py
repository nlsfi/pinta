# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_processing import core, exceptions


class MultiplyValues(core.Stage):
    """Multiply raster values by a specified factor."""

    def __init__(self, factor: float) -> None:
        self.factor = factor

    def process(self, data: core.RasterDataset) -> core.RasterDataset:
        """Multiply raster values by the specified factor."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=MultiplyValues.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )
        arr = data.array.copy()

        if data.nodata is not None:
            mask = arr != data.nodata
            arr[mask] = arr[mask] * self.factor
        else:
            arr = arr * self.factor

        return core.RasterDataset(
            array=arr, transform=data.transform, crs=data.crs, nodata=data.nodata
        )
