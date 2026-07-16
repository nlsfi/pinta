# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import copy
import dataclasses
import math

import affine
import geopandas
import numpy as np
import rasterio


@dataclasses.dataclass(frozen=True)
class RasterDataset:
    """Dataclass to pass raster data between processing stages."""

    array: np.ndarray
    transform: affine.Affine
    crs: str | None  # in format EPSG:xxxx
    nodata: float | int | None = None

    def __post_init__(self) -> None:
        """Force raster arrays to float32 after construction."""
        # Bypass frozen dataclass assignment for construction-time normalization.
        object.__setattr__(self, "array", self.array.astype(np.float32, copy=False))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the raster's map bounds as (left, bottom, right, top)."""
        height, width = self.array.shape
        left = self.transform.c
        top = self.transform.f
        right = left + self.transform.a * width
        bottom = top + self.transform.e * height
        return left, bottom, right, top

    @staticmethod
    def from_rasterio(src: rasterio.DatasetReader) -> "RasterDataset":
        """Construct dataset from rasterio reader."""
        array = src.read(1)
        return RasterDataset(
            array=array,
            transform=src.transform,
            crs=src.crs.to_string() if src.crs else None,
            nodata=src.nodata,
        )

    @staticmethod
    def empty(
        bounds: tuple[float, float, float, float],
        pixel_size: float,
        crs: str | None,
        nodata: float,
    ) -> "RasterDataset":
        """Construct an all-nodata dataset covering given bounds.

        The grid is snapped outward to the pixel lattice anchored at the map
        origin, so it aligns with other rasters using the same pixel size.
        """
        bounds_left, bounds_bottom, bounds_right, bounds_top = bounds
        left = math.floor(bounds_left / pixel_size) * pixel_size
        right = math.ceil(bounds_right / pixel_size) * pixel_size
        bottom = math.floor(bounds_bottom / pixel_size) * pixel_size
        top = math.ceil(bounds_top / pixel_size) * pixel_size

        transform = affine.Affine(pixel_size, 0.0, left, 0.0, -pixel_size, top)
        width = round((right - left) / pixel_size)
        height = round((top - bottom) / pixel_size)
        return RasterDataset(
            array=np.full((height, width), nodata, dtype=np.float32),
            transform=transform,
            crs=crs,
            nodata=nodata,
        )


@dataclasses.dataclass(frozen=True)
class VectorDataset:
    """Dataclass to pass vector data between processing stages."""

    geodataframe: geopandas.GeoDataFrame


type StageReturnType = (
    RasterDataset | VectorDataset | tuple["StageReturnType" | None, ...] | None
)


class Stage:
    """Base class for all processing stages."""

    def __or__(self, other: "Stage") -> "Pipeline":
        if isinstance(other, Pipeline):
            return Pipeline([self, *other.stages])
        return Pipeline([self, other])

    def process(self, data: StageReturnType) -> StageReturnType:
        """Process the input data and return the result."""
        raise NotImplementedError

    def execute(self) -> StageReturnType:
        """Execute the pipeline without input data.

        This is used as entrypoint for the pipeline.
        """
        return self.process(None)


class Pipeline(Stage):
    """Pipeline to chain multiple stages together."""

    def __init__(self, stages: list[Stage]) -> None:
        self.stages = stages

    def __or__(self, other: Stage) -> "Pipeline":
        if isinstance(other, Pipeline):
            return Pipeline([*self.stages, *other.stages])
        return Pipeline([*self.stages, other])

    def process(self, data: StageReturnType) -> StageReturnType:
        """Process the data through all stages serially in the pipeline."""
        context = data
        for stage in self.stages:
            context = stage.process(context)
        return context


class Tee(Stage):
    """Tee stage to branch the pipeline into multiple paths."""

    def __init__(self, *branches: Stage) -> None:
        self.branches = branches

    def process(self, data: StageReturnType) -> StageReturnType:
        """Process the data and send it to all branches."""
        for branch in self.branches:
            branch.process(copy.deepcopy(data))
        return data


class Zip(Stage):
    """Zip stage to combine multiple branches into one."""

    def __init__(self, *others: Stage) -> None:
        self.others = others

    def _run_others(self) -> tuple[StageReturnType, ...]:
        results: list[StageReturnType] = []
        for other in self.others:
            result = other.execute()
            results.append(result)
        return tuple(results)

    def process(self, data: StageReturnType) -> StageReturnType:
        """Process the pipelines and combine their results and input into a tuple."""
        others_results = self._run_others()
        if data is None:
            return others_results
        return (data, *others_results)
