# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid

import geopandas
import numpy as np
from rasterio import features
from scipy import ndimage
from shapely import geometry

from pinta_processing import core, exceptions

_EMPTY_CELL_VALUE = 0
_ID_COLUMN = "id"


class VectorizeRaster(core.Stage):
    """Convert a raster dataset into vector polygons scored by elevation variance.

    Identifies contiguous non-nodata, non-zero clusters using 4-connectivity
    labeling. Each cluster is polygonized and assigned a score based on the
    ratio of its per-cluster elevation standard deviation to the logarithm of
    its area.
    """

    def process(self, data: core.StageReturnType) -> core.VectorDataset:
        """Polygonize raster clusters and return a scored VectorDataset."""
        if not isinstance(data, core.RasterDataset):
            raise exceptions.InvalidStageInputError(
                stage_name=VectorizeRaster.__name__,
                expected_type=core.RasterDataset.__name__,
                received_type=type(data).__name__,
            )

        arr = data.array
        nodata = data.nodata

        mask = ~np.isnan(arr) & (arr != 0)
        if nodata is not None:
            mask &= arr != nodata

        structure = ndimage.generate_binary_structure(2, 1)
        labeled, count = ndimage.label(mask, structure=structure)

        labels = np.arange(1, count + 1)
        counts = np.maximum(ndimage.sum(mask, labeled, index=labels), 1)
        sums = ndimage.sum(arr, labeled, index=labels)
        sums_sq = ndimage.sum(arr**2, labeled, index=labels)
        abs_sums = ndimage.sum(np.abs(arr), labeled, index=labels)
        means = sums / counts
        stds = np.sqrt(np.maximum((sums_sq / counts) - means**2, 0))
        std_lookup: dict[float, float] = dict(zip(labels, stds, strict=True))
        abs_sum_lookup: dict[float, float] = dict(zip(labels, abs_sums, strict=True))

        polygons = []
        scores = []
        energy_sums = []
        for geom_dict, val in features.shapes(
            labeled.astype(np.int32), mask=mask, transform=data.transform
        ):
            if val > _EMPTY_CELL_VALUE:
                polygon = geometry.shape(geom_dict)
                std = std_lookup.get(val, 0.0)
                score = std / np.log1p(polygon.area)
                polygons.append(polygon)
                scores.append(float(score))
                energy_sums.append(float(abs_sum_lookup.get(val, 0.0)))

        geodataframe = geopandas.GeoDataFrame(
            {
                _ID_COLUMN: [uuid.uuid4() for _ in scores],
                "relevance_score": scores,
                "energy_sum": energy_sums,
            },
            geometry=polygons,
            crs=data.crs,
        )
        geodataframe = geodataframe.rename_geometry("geom")

        return core.VectorDataset(geodataframe=geodataframe)
