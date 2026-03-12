# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Temporary models."""

import uuid
from pathlib import Path
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from pinta_db.constants import MULTIPOLYGON, POLYGON
from pinta_db.env import SRID
from pinta_db.models.base import ManagementBase
from pinta_db_utils.model_utils import foreign_key


class ProductionArea(ManagementBase, table=True):
    """Production area for elevation production."""

    name: str
    geom: Any = Field(
        sa_column=Column(Geometry(MULTIPOLYGON, srid=SRID, nullable=False))
    )

    tiles: list["PointCloudTile"] = Relationship(back_populates="production_area")


class PointCloudTile(ManagementBase, table=True):
    """Point cloud tile for single lidar mission."""

    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))
    file_path: str

    production_area_id: uuid.UUID = Field(foreign_key=foreign_key(ProductionArea))
    production_area: "ProductionArea" = Relationship(back_populates="tiles")

    @property
    def file_path_(self) -> Path:
        """Path as a Path object."""
        return Path(self.file_path)
