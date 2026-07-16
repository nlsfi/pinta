# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np
from pinta_common import Settings
from rasterio import features
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry

from pinta_processing import core, exceptions


class RasterMask(core.Stage):
    """Mask the raster pixels inside a polygon to a constant elevation.

    Pixels whose centre falls inside the polygon are set to the given
    elevation. Without an input dataset a new raster is created from scratch:
    a DB_DEM_PIXEL_SIZE grid covering the polygon, DB_DEM_NODATA outside it.
    """

    def __init__(self, wkt: str, elevation: float) -> None:
        super().__init__()
        self.wkt = wkt
        self.elevation = elevation
        self._polygon = self._parse_polygon(wkt)

    @staticmethod
    def _parse_polygon(wkt: str) -> BaseGeometry:
        """Parse the mask WKT and ensure it is a polygon."""
        try:
            geometry = shapely_wkt.loads(wkt)
        except Exception as error:
            message = f"RasterMask polygon WKT could not be parsed: {error}"
            raise ValueError(message) from error

        if geometry.geom_type != "Polygon":
            message = f"RasterMask polygon must be a Polygon, got {geometry.geom_type}"
            raise ValueError(message)
        return geometry

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:
        """Mask the input raster, or an all-nodata raster when there is none."""
        dataset = (
            data
            if data is not None
            else core.RasterDataset.empty(
                bounds=self._polygon.bounds,
                pixel_size=float(Settings.DB_DEM_PIXEL_SIZE),
                crs=f"EPSG:{Settings.DB_SRID}",
                nodata=Settings.DB_DEM_NODATA,
            )
        )

        if not isinstance(dataset, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterMask.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(dataset).__name__,
            )

        array = dataset.array.copy()
        array[self._target_mask(array.shape, dataset.transform)] = self.elevation
        return core.RasterDataset(
            array=array,
            transform=dataset.transform,
            crs=dataset.crs,
            nodata=dataset.nodata,
        )

    def _target_mask(
        self, shape: tuple[int, ...], transform: affine.Affine
    ) -> np.ndarray:
        """Return the mask of pixels whose centre falls inside the polygon."""
        return features.rasterize(
            [(self._polygon, 1)],
            out_shape=shape,
            transform=transform,
            fill=0,
            all_touched=False,
            dtype="uint8",
        ).astype(bool)
