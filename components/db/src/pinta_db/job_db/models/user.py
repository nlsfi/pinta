# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, func, true
from sqlmodel import Field

from pinta_common import Settings
from pinta_db.common import base
from pinta_db.constants import POLYGON
from pinta_db.job_db.models import base as job_base


class UpdateArea(job_base.UserVectorBase, table=True):  # type: ignore[call-arg]
    """Final update area."""

    geom: Any = Field(
        sa_column=Column(Geometry(POLYGON, srid=Settings.DB_SRID, nullable=False))
    )
    dissolved_geom: Any = Field(
        sa_column=Column(Geometry(POLYGON, srid=Settings.DB_SRID, nullable=True))
    )
    elevation: float | None = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    dirty: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=true()),
    )
    registered_at: datetime.datetime | None = Field(default=None)


class UpdateAreaRestore(job_base.UserVectorBase, table=True):  # type: ignore[call-arg]
    """Dissolved geometry saved when an update area is deleted."""

    geom: Any = Field(
        sa_column=Column(Geometry(POLYGON, srid=Settings.DB_SRID, nullable=False))
    )
    created_at: datetime.datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )


class DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Reference raster."""


class O2DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""
