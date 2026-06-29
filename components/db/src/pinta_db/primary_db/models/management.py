# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Temporary models."""

import datetime
import enum
import uuid
from pathlib import Path
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field, Relationship

from pinta_db import utils
from pinta_db.common.base import BasePrimaryDb
from pinta_db.constants import MULTIPOLYGON, POLYGON
from pinta_db.env import SRID
from pinta_db.primary_db.models.base import ManagementBase


class ProcessingStatus(enum.StrEnum):
    """Processing status for a production area."""

    NOT_STARTED = "not_started"
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    FAILURE = "failure"


class ProductionArea(BasePrimaryDb, ManagementBase, table=True):  # type: ignore[call-arg]
    """Production area for elevation production."""

    name: str
    database_name: str | None = Field(default=None)
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.NOT_STARTED,
        sa_column=Column(
            ENUM(
                ProcessingStatus,
                name="processing_status",
                values_callable=lambda enum_cls: [status.value for status in enum_cls],
            ),
            nullable=False,
            server_default=ProcessingStatus.NOT_STARTED.value,
        ),
    )
    processing_status_last_updated: datetime.datetime | None = Field(default=None)
    geom: Any = Field(
        sa_column=Column(Geometry(MULTIPOLYGON, srid=SRID, nullable=False))
    )

    tiles: list["PointCloudTile"] = Relationship(
        back_populates="production_area", cascade_delete=True
    )


class PointCloudTile(BasePrimaryDb, ManagementBase, table=True):  # type: ignore[call-arg]
    """Point cloud tile for single lidar mission."""

    geom: Any = Field(sa_column=Column(Geometry(POLYGON, srid=SRID, nullable=False)))
    file_path: str

    production_area_id: uuid.UUID = Field(foreign_key=utils.foreign_key(ProductionArea))
    production_area: "ProductionArea" = Relationship(back_populates="tiles")

    @property
    def file_path_(self) -> Path:
        """Path as a Path object."""
        return Path(self.file_path)
