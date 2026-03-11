# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Base classes for the models."""

import re
import uuid
from typing import TYPE_CHECKING

from geoalchemy2.shape import to_shape
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel

from pinta_db.exceptions import MissingFieldError
from pinta_db.schemas import Schema

if TYPE_CHECKING:
    from shapely import Geometry

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


def _camel_to_snake(name: str) -> str:
    repl = r"\1_\2"
    return re.sub(
        r"([a-z0-9])([A-Z])", repl, re.sub(r"(.)([A-Z][a-z]+)", repl, name)
    ).lower()


class BaseModel(SQLModel):
    """Base model for everything."""

    @declared_attr.directive
    def __tablename__(self) -> str:
        return _camel_to_snake(self.__name__)

    @property
    def geom_shapely(self) -> "Geometry":
        """Return the geometry as a shapely object."""
        field = "geom"
        if not hasattr(self, field):
            raise MissingFieldError(field)
        return to_shape(self.geom)  # type: ignore[assignment,attr-defined]


class TemporaryBaseModel(BaseModel):
    """Base model for tables in temporary schema (delete later)."""

    __table_args__ = {"schema": Schema.TEMPORARY.value}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


BaseModel.metadata.naming_convention = NAMING_CONVENTION
