# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np

from pinta_processing import core, exceptions

_EXPECTED_INPUT_LENGTH = 2


class RasterDiff(core.Stage):
    """Compute the pixel difference of two raster datasets (first minus second).

    Inputs are validated to have identical shape, CRS, and geotransform. If
    either dataset carries a nodata value for a pixel, the corresponding result
    pixel is set to nodata as well.
    """

    def _validate_input(
        self, data: tuple[core.RasterDataset, core.RasterDataset]
    ) -> None:
        if (
            not isinstance(data, tuple)
            or len(data) != _EXPECTED_INPUT_LENGTH
            or not isinstance(data[0], core.RasterDataset)
            or not isinstance(data[1], core.RasterDataset)
        ):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterDiff.__name__,
                expected_type="tuple[RasterDataset, RasterDataset]",
                received_type=type(data).__name__,
            )

        first, second = data

        if first.array.shape != second.array.shape:
            msg = (
                f"RasterDiff requires identical raster sizes, "
                f"got {first.array.shape} and {second.array.shape}"
            )
            raise ValueError(msg)

        if first.crs != second.crs:
            msg = (
                f"RasterDiff requires identical raster CRS, "
                f"got {first.crs!r} and {second.crs!r}"
            )
            raise ValueError(msg)

        if first.transform != second.transform:
            msg = (
                f"RasterDiff requires identical raster locations (transform), "
                f"got {first.transform} and {second.transform}"
            )
            raise ValueError(msg)

        if not np.issubdtype(first.array.dtype, np.floating):
            msg = (
                f"RasterDiff requires floating-point raster dtype, "
                f"got {first.array.dtype} for first raster"
            )
            raise ValueError(msg)

        if not np.issubdtype(second.array.dtype, np.floating):
            msg = (
                f"RasterDiff requires floating-point raster dtype, "
                f"got {second.array.dtype} for second raster"
            )
            raise ValueError(msg)

        if first.array.dtype != second.array.dtype:
            msg = (
                f"RasterDiff requires identical raster dtypes, "
                f"got {first.array.dtype} and {second.array.dtype}"
            )
            raise ValueError(msg)

    def process(
        self,
        data: tuple[core.RasterDataset, core.RasterDataset],
    ) -> core.RasterDataset:
        """Subtract the second raster from the first and return the result."""
        self._validate_input(data)

        first, second = data

        nodata = first.nodata if first.nodata is not None else second.nodata

        nodata_mask = np.zeros(first.array.shape, dtype=bool)
        if first.nodata is not None:
            nodata_mask |= first.array == first.nodata
        if second.nodata is not None:
            nodata_mask |= second.array == second.nodata

        result = first.array - second.array

        if nodata is not None:
            result[nodata_mask] = nodata

        return core.RasterDataset(
            array=result,
            transform=first.transform,
            crs=first.crs,
            nodata=nodata,
        )
