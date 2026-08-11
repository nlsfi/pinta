# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any

import geopandas
import numpy as np
import pandas as pd
from pinta_common import Settings
from pinta_db.job_db.models import reference
from pinta_db.primary_db.models import dem
from pinta_db_utils import model_utils
from shapely import wkt as shapely_wkt
from sqlmodel import Session

from pinta_processing import reader
from pinta_processing.reader import ogr

LOGGER = logging.getLogger(__name__)

LAKE_PART_LAYER = "lake_part"
LAKE_PART_ELEVATION_ATTRIBUTES = ("average_water_level", "surveyed_water_level")
SEA_PART_LAYER = "sea_part"
SEA_PART_ELEVATION = 0.12

POLYGON_GEOMETRY_TYPES = ("Polygon", "MultiPolygon")

RASTER_FLAT_ELEVATION_TOLERANCE = 0.0


def find_mask_polygons(
    sources: Sequence[reader.OgrSource],
    area_of_interest: str | None = None,
) -> list[dict[str, Any]]:
    """Read the given mask sources into polygons with a resolved elevation.

    Only (multi)polygons are kept, and they come out as single 2D polygons in
    the project CRS. Polygons outside `area_of_interest` (when given) and polygons
    whose elevation cannot be resolved are dropped.
    """
    frame = _filter_to_polygons_only(reader.read_ogr_geodataframe(sources))
    if area_of_interest is not None:
        frame = frame[frame.intersects(shapely_wkt.loads(area_of_interest))]

    polygons = []
    for _, row in frame.iterrows():
        if polygon := _build_mask_polygon_with_elevation(row):
            polygons.append(polygon)

    return polygons


def _filter_to_polygons_only(
    data_frame: geopandas.GeoDataFrame,
) -> geopandas.GeoDataFrame:
    """Reduce the sources to the single 2D polygons the masks are made of."""
    polygons = data_frame[
        data_frame.geometry.notna()
        & ~data_frame.geometry.is_empty
        & data_frame.geom_type.isin(POLYGON_GEOMETRY_TYPES)
    ]
    polygons = polygons.set_geometry(polygons.geometry.force_2d())
    return polygons.explode(index_parts=False)


def _resolve_elevation(
    source_layer: str, attributes: Mapping[str, Any]
) -> float | None:
    if source_layer == SEA_PART_LAYER:
        return SEA_PART_ELEVATION

    if source_layer == LAKE_PART_LAYER:
        for attribute in LAKE_PART_ELEVATION_ATTRIBUTES:
            value = attributes.get(attribute)
            if value is not None and not pd.isna(value):
                return float(value)

    return None


def insert_update_area_suggestions_with_elevation(
    primary_session: Session,
    job_session: Session,
    sources: Sequence[reader.OgrSource],
    area_of_interest: str | None = None,
) -> list[reference.UpdateAreaSuggestion]:
    """Insert a suggestion for every mask the DEM does not model as flat.

    Masks are checked independently so one mask the DEM cannot cover doesn't
    discard suggestions from every other mask. Successful suggestions are
    committed and any failures are raised.
    """
    suggestions = []
    failures: list[str] = []

    for polygon in find_mask_polygons(sources, area_of_interest):
        try:
            suggestion = build_update_area_suggestions(primary_session, **polygon)
        except ValueError as error:
            centroid = shapely_wkt.loads(polygon["geom_wkt"]).centroid.wkt
            failures.append(f"{polygon['source_layer']} at {centroid}: {error}")
            continue

        if suggestion is not None:
            suggestions.append(suggestion)

    job_session.add_all(suggestions)
    job_session.commit()

    if failures:
        msg = (
            f"{len(failures)} mask(s) could not be checked against the DEM:\n"
            + "\n".join(failures)
        )
        raise ValueError(msg)

    return suggestions


def build_update_area_suggestions(
    primary_session: Session,
    geom_wkt: str,
    elevation: float,
    source_layer: str,
) -> reference.UpdateAreaSuggestion | None:
    """Build an update area suggestion when the DEM inside the polygon is uneven."""
    raster_pixels = _read_raster_values(primary_session, geom_wkt)
    if raster_pixels.size == 0:
        schema, table = model_utils.schema_and_table(dem.Dem)
        msg = (
            f"A {source_layer} mask has no elevations in "
            f"{schema}.{table}: every pixel inside it is nodata"
        )
        raise ValueError(msg)

    if is_flat(raster_pixels):
        return None

    return reference.UpdateAreaSuggestion(
        geom=f"SRID={Settings.DB_SRID};{geom_wkt}",
        elevation=elevation,
    )


def _read_raster_values(primary_session: Session, geom_wkt: str) -> np.ndarray:
    schema, table = model_utils.schema_and_table(dem.Dem)
    dataset = reader.PostgisReader(schema, table, primary_session, geom_wkt).process(
        None
    )

    valid = ~np.isnan(dataset.array)
    if dataset.nodata is not None and not math.isnan(dataset.nodata):
        valid &= dataset.array != dataset.nodata
    return dataset.array[valid]


def is_flat(
    elevations: np.ndarray, tolerance: float = RASTER_FLAT_ELEVATION_TOLERANCE
) -> bool:
    """Return True when every elevation is the same within the tolerance."""
    return bool(elevations.max() - elevations.min() <= tolerance)


def _build_mask_polygon_with_elevation(row: Mapping[str, Any]) -> dict[str, Any] | None:
    geometry, source_layer = row[ogr.GEOMETRY_COLUMN], row[ogr.SOURCE_LAYER_NAME_COLUMN]

    elevation = _resolve_elevation(source_layer, row)
    if elevation is None:
        LOGGER.info(
            "Skipping a %s polygon at %s: its elevation cannot be resolved",
            source_layer,
            geometry.centroid.wkt,
        )
        return None

    return {
        "geom_wkt": geometry.wkt,
        "elevation": elevation,
        "source_layer": source_layer,
    }
