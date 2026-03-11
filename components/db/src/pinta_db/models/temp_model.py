# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Temporary models."""

import uuid
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from pinta_db.constants import LINESTRING, POINT
from pinta_db.env import SRID
from pinta_db.models.base import TemporaryBaseModel
from pinta_db.utils.model_utils import foreign_key


class TemporaryModel(TemporaryBaseModel, table=True):  # type: ignore[call-arg]
    """Temp model, remove when adding real models."""

    geom: Any = Field(sa_column=Column(Geometry(POINT, srid=SRID, nullable=False)))
    text: str | None  # Nullable
    number: int  # not-null
    # Have to use Optional with a quoted class
    temp_2: Optional["TemporaryModelWithForeignKey"] = Relationship(
        back_populates="temp"
    )


class TemporaryModelWithForeignKey(TemporaryBaseModel, table=True):  # type: ignore[call-arg]
    """Temp model, remove when adding real models."""

    geom: Any = Field(sa_column=Column(Geometry(LINESTRING, srid=SRID, nullable=False)))

    temp_id: uuid.UUID = Field(foreign_key=foreign_key(TemporaryModel))
    temp: "TemporaryModel" = Relationship(back_populates="temp_2")
