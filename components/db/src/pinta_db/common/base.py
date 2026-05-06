# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Base classes for the models."""

import re
from typing import Any

from geoalchemy2 import Raster
from sqlalchemy import MetaData, orm
from sqlmodel import BigInteger, Field, SQLModel

from pinta_db.exceptions import MissingFieldError

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


def _camel_to_snake(name: str) -> str:
    # Add underscore before capital letters
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Add underscore between lowercase/number and uppercase
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Add underscore between letters and numbers
    name = re.sub(r"([a-zA-Z])([0-9])", r"\1_\2", name)
    return name.lower()


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


class RasterBase(BaseModel):
    """Base model for raster tables."""

    rid: int = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"autoincrement": True},
        sa_type=BigInteger,
    )
    rast: Any = Field(
        default=None,
        sa_type=Raster,
        nullable=False,
    )


primary_db_metadata = MetaData()
job_db_metadata = MetaData()


class BasePrimaryDb(BaseModel):
    """Base model for primary db tables."""

    metadata = primary_db_metadata


class BaseJobDb(BaseModel):
    """Base model for job db tables."""

    metadata = job_db_metadata


BaseModel.metadata.naming_convention = NAMING_CONVENTION
