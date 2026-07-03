# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
from rasterio import features
from scipy.interpolate import griddata
from scipy.ndimage import binary_dilation, generate_binary_structure
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry

from pinta_processing import core, exceptions

_MIN_KNOWN_POINTS = 4
_SAMPLING_MARGIN = 5


class RasterInterpolate(core.Stage):
    """Interpolate the raster pixels inside a polygon with cubic interpolation.

    Pixels whose centre falls inside the polygon are recomputed with SciPy's
    cubic griddata interpolation from the surrounding valid pixels. The raster
    must hold enough valid data around the polygon for every target pixel
    to fall within the interpolation domain.
    """

    def __init__(self, wkt: str) -> None:
        super().__init__()
        self.wkt = wkt
        self._polygon = self._parse_polygon(wkt)

    @staticmethod
    def _parse_polygon(wkt: str) -> BaseGeometry:
        """Parse the interpolation WKT and ensure it is a polygon."""
        try:
            geometry = shapely_wkt.loads(wkt)
        except Exception as error:
            message = f"RasterInterpolate polygon WKT could not be parsed: {error}"
            raise ValueError(message) from error

        if geometry.geom_type != "Polygon":
            message = (
                f"RasterInterpolate polygon must be a Polygon, got {geometry.geom_type}"
            )
            raise ValueError(message)
        return geometry

    def process(self, data: core.RasterDataset) -> core.RasterDataset:
        """Interpolate the pixels inside the polygon and return the raster."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=RasterInterpolate.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        array = data.array.astype(np.float64, copy=True)
        if data.nodata is not None:
            array[array == data.nodata] = np.nan

        target_mask = features.rasterize(
            [(self._polygon, 1)],
            out_shape=array.shape,
            transform=data.transform,
            fill=0,
            all_touched=False,
            dtype="uint8",
        ).astype(bool)

        interpolated = self._interpolate(array, target_mask)

        result = array.copy()
        result[target_mask] = interpolated
        if data.nodata is not None:
            result[np.isnan(result)] = data.nodata

        return core.RasterDataset(
            array=result,
            transform=data.transform,
            crs=data.crs,
            nodata=data.nodata,
        )

    def _interpolate(self, array: np.ndarray, target_mask: np.ndarray) -> np.ndarray:
        """Cubic-interpolate the target pixels from surrounding valid data."""
        if not target_mask.any():
            message = "RasterInterpolate polygon does not cover any raster pixels"
            raise ValueError(message)

        known_mask = self._sampling_mask(target_mask) & ~np.isnan(array) & ~target_mask
        if int(known_mask.sum()) < _MIN_KNOWN_POINTS:
            message = (
                "RasterInterpolate has too little data around the polygon to "
                "interpolate"
            )
            raise ValueError(message)

        rows, cols = np.indices(array.shape)
        points = np.column_stack((rows[known_mask], cols[known_mask]))
        values = array[known_mask]
        targets = np.column_stack((rows[target_mask], cols[target_mask]))

        interpolated = griddata(points, values, targets, method="cubic")

        if np.isnan(interpolated).any():
            message = (
                "RasterInterpolate has too little data around the polygon to "
                "interpolate"
            )
            raise ValueError(message)
        return interpolated

    @staticmethod
    def _sampling_mask(target_mask: np.ndarray) -> np.ndarray:
        """Return the band of pixels around the polygon used for sampling."""
        structure = generate_binary_structure(2, 2)
        return binary_dilation(
            target_mask, structure=structure, iterations=_SAMPLING_MARGIN
        )
