# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Base classes for the models."""

import re
import uuid

from sqlalchemy import orm
from sqlmodel import Field, SQLModel

from pinta_db.exceptions import MissingFieldError
from pinta_db.schemas import Schema

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

    @orm.declared_attr.directive
    def __tablename__(self) -> str:
        return _camel_to_snake(self.__name__)

    @property
    def geom_wkt(self) -> str:
        """Return the geometry as wkt."""
        try:
            import geoalchemy2.shape  # noqa: PLC0415
        except ImportError as e:
            message = "Install pinta-db[shapely] extra to use this feature"
            raise ImportError(message) from e

        field = "geom"
        if not hasattr(self, field):
            raise MissingFieldError(field)

        # Geometry can be either a string (unsaved model) or a
        # geoalchemy2.WKBElement | WKTElement (saved model)
        geom = getattr(self, field)
        if isinstance(geom, str):
            return geom  # type: ignore[assignment,attr-defined]
        return geoalchemy2.shape.to_shape(geom).wkt  # type: ignore[assignment,attr-defined]


class ManagementBase(BaseModel):
    """Base model for tables in management schema."""

    __table_args__ = {"schema": Schema.MANAGEMENT.value}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


BaseModel.metadata.naming_convention = NAMING_CONVENTION
