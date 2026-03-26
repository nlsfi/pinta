# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import copy
import dataclasses

import affine
import numpy as np
import rasterio


@dataclasses.dataclass(frozen=True)
class RasterDataset:
    """Dataclass to pass raster data between processing stages."""

    array: np.ndarray
    transform: affine.Affine
    crs: str | None
    nodata: float | int | None = None

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


class Stage:
    """Base class for all processing stages."""

    def __or__(self, other: "Stage") -> "Pipeline":
        if isinstance(other, Pipeline):
            return Pipeline([self, *other.stages])
        return Pipeline([self, other])

    def process(self, data: RasterDataset | None) -> RasterDataset | None:
        """Process the input data and return the result."""
        raise NotImplementedError


class Pipeline(Stage):
    """Pipeline to chain multiple stages together."""

    def __init__(self, stages: list[Stage]) -> None:
        self.stages = stages

    def __or__(self, other: Stage) -> "Pipeline":
        if isinstance(other, Pipeline):
            return Pipeline([*self.stages, *other.stages])
        return Pipeline([*self.stages, other])

    def process(self, data: RasterDataset | None) -> RasterDataset | None:
        """Process the data through all stages serially in the pipeline."""
        context = data
        for stage in self.stages:
            context = stage.process(context)
        return context

    def execute(self) -> RasterDataset | None:
        """Execute the pipeline without input data.

        This is used as entrypoint for the pipeline.
        """
        return self.process(None)


class Tee(Stage):
    """Tee stage to branch the pipeline into multiple paths."""

    def __init__(self, *branches: Stage) -> None:
        self.branches = branches

    def process(self, data: RasterDataset | None) -> RasterDataset | None:
        """Process the data and send it to all branches."""
        for branch in self.branches:
            branch.process(copy.deepcopy(data))
        return data
