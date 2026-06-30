# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field

from pinta_common import Settings
from pinta_db.constants import POLYGON
from pinta_db.job_db.models.base import UserBase


class UpdateArea(UserBase, table=True):  # type: ignore[call-arg]
    """Final update area."""

    geom: Any = Field(
        sa_column=Column(Geometry(POLYGON, srid=Settings.DB_SRID, nullable=False))
    )
