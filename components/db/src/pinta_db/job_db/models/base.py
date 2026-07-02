# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import uuid

from sqlmodel import Field

from pinta_db.common.base import BaseJobDb
from pinta_db.job_db.schema import Schema


class ReferenceBase(BaseJobDb):
    """Base model for tables in reference schema."""

    __table_args__ = {"schema": Schema.REFERENCE.value}  # noqa: RUF012


class UserBase(BaseJobDb):
    """Base model for tables in user schema."""

    __table_args__ = {"schema": Schema.USER.value}  # noqa: RUF012


class UserVectorBase(UserBase):
    """Base model for tables in user schema."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
