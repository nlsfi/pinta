# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column
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


class DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Reference raster."""


class O2DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 2."""


class O8DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 8."""


class O128DemPreview(job_base.UserBase, base.RasterBase, table=True):  # type: ignore[call-arg]
    """Overview factor 128."""
