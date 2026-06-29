# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid
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


class O2Dem(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8Dem(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128Dem(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""


class DiffGtThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Difference raster above threshold."""


class O2DiffGtThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8DiffGtThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128DiffGtThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""


class DiffLteThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Difference raster from changes at or below threshold."""


class O2DiffLteThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8DiffLteThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128DiffLteThreshold(ReferenceBase, RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""


class DiffPolygon(ReferenceBase, table=True):  # type: ignore[call-arg]
    """Difference polygon."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    relevance_score: float | None = Field(sa_column=Column(Float, nullable=True))
    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))


class DiffPolygonCluster(ReferenceBase, table=True):  # type: ignore[call-arg]
    """Cluster of Difference polygons."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    energy_sum: float | None = Field(sa_column=Column(Float, nullable=True))
    energy_distribution: float | None = Field(sa_column=Column(Float, nullable=True))
    cluster_area: float | None = Field(sa_column=Column(Float, nullable=True))
    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))
