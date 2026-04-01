# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Database schemas and privileges."""

import enum

from pydantic import dataclasses


class Schema(enum.Enum):
    """Schemas used in the database."""

    MIGRATIONS = "alembic"
    MANAGEMENT = "management"
    # TODO: replace this with a schema where processing tables are stored
    PROCESSING = "processing"


# Role placeholders
class Role(enum.Enum):
    """Roles used in the database."""

    WRITER = "writer"
    READER = "reader"
    PROCESSING_WORKER = "processing_worker"


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


@dataclasses.dataclass(frozen=True)
class RolePrivileges:
    """Role privileges for a specific schema."""

    role: Role
    usage: bool = True
    table_privileges: tuple[Privilege, ...] = ()
    sequence_privileges: tuple[Privilege, ...] = ()
    default_table_privileges: tuple[Privilege, ...] = ()
    default_sequence_privileges: tuple[Privilege, ...] = ()

    @staticmethod
    def get_default_write_privileges(role: Role) -> "RolePrivileges":
        """Get default write privileges for the role."""
        return RolePrivileges(
            role=role,
            table_privileges=(
                Privilege.SELECT,
                Privilege.INSERT,
                Privilege.UPDATE,
                Privilege.DELETE,
            ),
            sequence_privileges=(
                Privilege.USAGE,
                Privilege.SELECT,
                Privilege.UPDATE,
            ),
            default_table_privileges=(
                Privilege.SELECT,
                Privilege.INSERT,
                Privilege.UPDATE,
                Privilege.DELETE,
            ),
            default_sequence_privileges=(
                Privilege.USAGE,
                Privilege.SELECT,
                Privilege.UPDATE,
            ),
        )


@dataclasses.dataclass(frozen=True)
class SchemaConfig:
    """Schema configuration."""

    schema: Schema
    owner_privileges: tuple[Privilege, ...] = (Privilege.USAGE, Privilege.CREATE)
    role_privileges: tuple[RolePrivileges, ...] = ()
    extra_schema_owners: tuple[str, ...] = ()


SCHEMA_CONFIGURATIONS = [
    SchemaConfig(
        schema=Schema.MANAGEMENT,
        role_privileges=(
            RolePrivileges.get_default_write_privileges(Role.WRITER),
            RolePrivileges(
                role=Role.READER,
                table_privileges=(Privilege.SELECT,),
                sequence_privileges=(
                    Privilege.USAGE,
                    Privilege.SELECT,
                ),
                default_table_privileges=(Privilege.SELECT,),
                default_sequence_privileges=(Privilege.USAGE, Privilege.SELECT),
            ),
        ),
    ),
    SchemaConfig(
        schema=Schema.MIGRATIONS,
    ),
    SchemaConfig(
        schema=Schema.PROCESSING,
        extra_schema_owners=("pinta_processing_worker",),
        role_privileges=(
            RolePrivileges.get_default_write_privileges(Role.PROCESSING_WORKER),
        ),
    ),
]
