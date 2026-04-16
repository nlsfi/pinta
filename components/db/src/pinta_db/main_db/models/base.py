# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid

from sqlmodel import Field

from pinta_db.common.base import BaseModel, RasterBase
from pinta_db.schemas import Schema


class ManagementBase(BaseModel):
    """Base model for tables in management schema."""

    __table_args__ = {"schema": Schema.MANAGEMENT.value}  # noqa: RUF012

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class DemBase(RasterBase):
    """Base model for tables in dem schema."""

    __table_args__ = {"schema": Schema.DEM.value}  # noqa: RUF012
