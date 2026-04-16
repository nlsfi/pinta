# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column, Float
from sqlmodel import Field

from pinta_db.common.base import RasterBase
from pinta_db.constants import POLYGON
from pinta_db.env import SRID
from pinta_db.job_db.models.base import ReferenceBase


class Dem(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Reference raster."""


class Diff(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Difference raster."""


class DiffDior(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Difference raster from changes below limit value."""


class DiffPolygon(ReferenceBase, table=True):  # type: ignore[call-arg]
    """Difference polygon."""

    relevance_score: float | None = Field(sa_column=Column(Float, nullable=True))
    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))


class DiffPolygonCluster(ReferenceBase, table=True):  # type: ignore[call-arg]
    """Cluster of Difference polygons."""

    energy_sum: float | None = Field(sa_column=Column(Float, nullable=True))
    energy_distribution: float | None = Field(sa_column=Column(Float, nullable=True))
    cluster_area: float | None = Field(sa_column=Column(Float, nullable=True))
    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))
