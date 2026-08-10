# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import dataclasses
import logging
from collections.abc import Sequence

import geopandas
import pandas as pd
from pinta_common import Settings

from pinta_processing import core, exceptions

LOGGER = logging.getLogger(__name__)

GEOMETRY_COLUMN = "geom"


@dataclasses.dataclass(frozen=True)
class OgrSource:
    """One vector data source to read.

    `data_source` is handed to GDAL/OGR verbatim, so anything the installed
    drivers understand works.
    """

    data_source: str
    layer: str | None = None  # None reads every spatial layer of the source


class OgrReader(core.Stage):
    """Read the given vector data sources as a single vector dataset."""

    def __init__(self, sources: Sequence[OgrSource], crs: str | None = None) -> None:
        super().__init__()
        self.sources = sources
        self.crs = crs

    def process(self, data: core.StageReturnType) -> core.VectorDataset:  # noqa: ARG002
        """Read the data sources into a VectorDataset."""
        return core.VectorDataset(
            geodataframe=read_ogr_geodataframe(self.sources, crs=self.crs)
        )


def read_ogr_geodataframe(
    sources: Sequence[OgrSource], crs: str | None = None
) -> geopandas.GeoDataFrame:
    """Read every given data source into a single GeoDataFrame.

    Each source is reprojected into the project CRS (unless
    `crs` argument overrides it) and the sources are stacked into
    one frame holding the union of all their attributes.
    """
    target_crs = crs if crs is not None else f"EPSG:{Settings.DB_SRID}"

    frames = [
        _read_layer(source, layer, target_crs)
        for source in sources
        for layer in _find_layers(source)
    ]
    if not frames:
        LOGGER.warning("No vector data sources given, returning an empty frame")
        return _empty_geodataframe(target_crs)

    combined = pd.concat(frames, ignore_index=True, join="outer")
    return geopandas.GeoDataFrame(combined, geometry=GEOMETRY_COLUMN, crs=target_crs)


def _find_layers(source: OgrSource) -> list[str]:
    if source.layer is not None:
        return [source.layer]

    try:
        layers = geopandas.list_layers(source.data_source)
    except Exception as error:
        raise exceptions.OgrSourceError(
            source=source.data_source, reason=str(error)
        ) from error

    layers_with_geometry = [
        str(name)
        for name, geometry_type in zip(
            layers["name"], layers["geometry_type"], strict=True
        )
        if pd.notna(geometry_type)
    ]
    if not layers_with_geometry:
        raise exceptions.OgrSourceError(
            source=source.data_source,
            reason="source has no layers with geometries",
        )
    LOGGER.info("Reading layers %s of %s", layers_with_geometry, source.data_source)
    return layers_with_geometry


def _read_layer(
    source: OgrSource, layer: str, target_crs: str
) -> geopandas.GeoDataFrame:
    """Read one layer through GDAL and normalize it into the target CRS."""
    label = f"{source.data_source} (layer {layer!r})"
    try:
        frame = geopandas.read_file(source.data_source, layer=layer)
    except Exception as error:
        raise exceptions.OgrSourceError(source=label, reason=str(error)) from error

    if not isinstance(frame, geopandas.GeoDataFrame):
        raise exceptions.OgrSourceError(source=label, reason="layer has no geometry")

    if frame.crs is None:
        raise exceptions.OgrSourceError(
            source=label,
            reason=f"source has no CRS, it cannot be reprojected into {target_crs}",
        )
    if frame.crs != target_crs:
        frame = frame.to_crs(target_crs)

    if frame.geometry.name != GEOMETRY_COLUMN and GEOMETRY_COLUMN in frame.columns:
        raise exceptions.OgrSourceError(
            source=label,
            reason=(
                f"source has an attribute named {GEOMETRY_COLUMN!r}, which "
                "collides with the geometry column of the combined frame"
            ),
        )
    return frame.rename_geometry(GEOMETRY_COLUMN)


def _empty_geodataframe(crs: str) -> geopandas.GeoDataFrame:
    """Return an empty frame holding only the geometry column."""
    return geopandas.GeoDataFrame(
        {GEOMETRY_COLUMN: geopandas.GeoSeries([], crs=crs)},
        geometry=GEOMETRY_COLUMN,
        crs=crs,
    )
