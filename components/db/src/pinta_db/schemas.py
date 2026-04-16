# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Database schemas and privileges."""

import dataclasses
import enum


class Schema(enum.Enum):
    """Schemas used in the database."""

    MIGRATIONS = "alembic"
    MANAGEMENT = "management"
    # TODO: replace this with a schema where processing tables are stored
    PROCESSING = "processing"
    DEM = "dem"
    REFERENCE = "reference"
    USER = "user_data"


# Role placeholders
class Role(enum.Enum):
    """Roles used in the database."""

    OWNER = enum.auto()
    WRITER = enum.auto()
    READER = enum.auto()
    PROCESSING_WORKER = enum.auto()


class Privilege(enum.Enum):
    """PostgreSQL privileges for the roles."""

    USAGE = enum.auto()
    CREATE = enum.auto()
    SELECT = enum.auto()
    INSERT = enum.auto()
    UPDATE = enum.auto()
    DELETE = enum.auto()
    TRUNCATE = enum.auto()
    REFERENCES = enum.auto()
    TRIGGER = enum.auto()
    EXECUTE = enum.auto()


class AccessLevel(enum.Enum):
    """Named access pattern that expands into concrete privileges."""

    READ = enum.auto()
    READ_WRITE = enum.auto()
    MANAGE = enum.auto()

    @property
    def privileges(self) -> "LevelPrivileges":
        """Concrete table, sequence, and schema privileges for this level."""
        return _LEVEL_PRIVILEGES[self]


@dataclasses.dataclass(frozen=True)
class LevelPrivileges:
    """Concrete privileges that `AccessLevel` expands into."""

    tables: tuple[Privilege, ...]
    sequences: tuple[Privilege, ...]
    # Schema privileges beyond the always-granted USAGE.
    schema_extra: tuple[Privilege, ...]


_WRITE_TABLE_PRIVILEGES: tuple[Privilege, ...] = (
    Privilege.SELECT,
    Privilege.INSERT,
    Privilege.UPDATE,
    Privilege.DELETE,
    Privilege.TRUNCATE,
)
_WRITE_SEQUENCE_PRIVILEGES: tuple[Privilege, ...] = (
    Privilege.USAGE,
    Privilege.SELECT,
    Privilege.UPDATE,
)

_LEVEL_PRIVILEGES: dict[AccessLevel, LevelPrivileges] = {
    AccessLevel.READ: LevelPrivileges(
        tables=(Privilege.SELECT,),
        sequences=(Privilege.USAGE, Privilege.SELECT),
        schema_extra=(),
    ),
    AccessLevel.READ_WRITE: LevelPrivileges(
        tables=_WRITE_TABLE_PRIVILEGES,
        sequences=_WRITE_SEQUENCE_PRIVILEGES,
        schema_extra=(),
    ),
    AccessLevel.MANAGE: LevelPrivileges(
        tables=_WRITE_TABLE_PRIVILEGES,
        sequences=_WRITE_SEQUENCE_PRIVILEGES,
        schema_extra=(Privilege.CREATE,),
    ),
}


@dataclasses.dataclass(frozen=True)
class SchemaAccess:
    """Grant a role the given access level to a schema and its objects."""

    role: Role
    level: AccessLevel


@dataclasses.dataclass(frozen=True)
class DelegatedAccess:
    """Grant access on objects that another role creates."""

    creator: Role
    grantee: Role
    level: AccessLevel
    # When True, `grantee` may re-grant these privileges to other roles.
    with_grant_option: bool = False


@dataclasses.dataclass(frozen=True)
class SchemaConfig:
    """Schema configuration."""

    schema: Schema
    owner: Role = Role.OWNER
    access: tuple[SchemaAccess, ...] = ()
    delegated: tuple[DelegatedAccess, ...] = ()
