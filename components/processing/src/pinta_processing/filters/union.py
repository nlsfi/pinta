# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import math

import affine
import numpy as np

from pinta_processing import core, exceptions

# Relative tolerance for comparing pixel sizes across datasets.
_PIXEL_SIZE_RELATIVE_TOLERANCE = 1e-9


class RasterUnion(core.Stage):
    """Union several aligned raster datasets into one, the last dataset winning.

    Concat input rasters to a single raster covering the union of their extents. For
    individual pixels last non nodata value wins.

    The inputs must already share the same CRS and pixel size; this stage neither
    reprojects nor resamples and raises if they do not match.
    """

    def process(self, data: tuple[core.RasterDataset, ...]) -> core.RasterDataset:
        """Merge the input rasters over their union, the last dataset winning."""
        datasets = self._validate_input(data)
        self._validate_alignment(datasets)

        transform, height, width = self._build_merged_transform(datasets)

        merged = np.full((height, width), np.nan, dtype=np.float64)
        for dataset in datasets:
            placed = self._place_on_grid(dataset, transform, height, width)
            valid = ~np.isnan(placed)
            merged[valid] = placed[valid]

        nodata = next((d.nodata for d in datasets if d.nodata is not None), None)
        if nodata is not None:
            merged[np.isnan(merged)] = nodata

        return core.RasterDataset(
            array=merged,
            transform=transform,
            crs=datasets[0].crs,
            nodata=nodata,
        )

    @staticmethod
    def _validate_input(
        data: tuple[core.RasterDataset, ...],
    ) -> tuple[core.RasterDataset, ...]:
        """Ensure the input is a non-empty tuple of raster datasets."""
        if (
            not isinstance(data, tuple)
            or len(data) == 0
            or not all(isinstance(item, core.RasterDataset) for item in data)
        ):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterUnion.__name__,
                expected_type="tuple[RasterDataset, ...]",
                received_type=type(data).__name__,
            )
        return data

    @staticmethod
    def _validate_alignment(datasets: tuple[core.RasterDataset, ...]) -> None:
        """Ensure all datasets share the same CRS and pixel size."""
        reference = datasets[0]
        for dataset in datasets[1:]:
            if dataset.crs != reference.crs:
                msg = (
                    "RasterUnion inputs must share the same CRS, got "
                    f"{reference.crs} and {dataset.crs}"
                )
                raise ValueError(msg)
            if not (
                math.isclose(
                    dataset.transform.a,
                    reference.transform.a,
                    rel_tol=_PIXEL_SIZE_RELATIVE_TOLERANCE,
                )
                and math.isclose(
                    dataset.transform.e,
                    reference.transform.e,
                    rel_tol=_PIXEL_SIZE_RELATIVE_TOLERANCE,
                )
            ):
                msg = (
                    "RasterUnion inputs must share the same pixel size, got "
                    f"({reference.transform.a}, {reference.transform.e}) and "
                    f"({dataset.transform.a}, {dataset.transform.e})"
                )
                raise ValueError(msg)

    @staticmethod
    def _to_nan_array(dataset: core.RasterDataset) -> np.ndarray:
        """Return the raster values as float64 with nodata replaced by nan."""
        array = dataset.array.astype(np.float64, copy=True)
        if dataset.nodata is not None:
            array[array == dataset.nodata] = np.nan
        return array

    def _build_merged_transform(
        self, datasets: tuple[core.RasterDataset, ...]
    ) -> tuple[affine.Affine, int, int]:
        """Build the transform and shape of the grid covering all datasets."""
        lefts, bottoms, rights, tops = zip(
            *(dataset.bounds for dataset in datasets), strict=True
        )
        left = min(lefts)
        top = max(tops)
        right = max(rights)
        bottom = min(bottoms)
        transform = affine.Affine(
            datasets[0].transform.a, 0.0, left, 0.0, datasets[0].transform.e, top
        )
        width = round((right - left) / transform.a)
        height = round((bottom - top) / transform.e)
        return transform, height, width

    def _place_on_grid(
        self,
        dataset: core.RasterDataset,
        transform: affine.Affine,
        height: int,
        width: int,
    ) -> np.ndarray:
        """Position dataset inside given grid, filling gaps with nan."""
        col_offset = round((dataset.transform.c - transform.c) / transform.a)
        row_offset = round((dataset.transform.f - transform.f) / transform.e)
        grid = np.full((height, width), np.nan, dtype=np.float64)
        source = self._to_nan_array(dataset)
        source_height, source_width = source.shape
        grid[
            row_offset : row_offset + source_height,
            col_offset : col_offset + source_width,
        ] = source
        return grid
