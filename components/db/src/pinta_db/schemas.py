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


@dataclasses.dataclass(frozen=True)
class RolePrivileges:
    """Role privileges for a specific schema."""

    role: Role
    usage: bool = True
    table_privileges: tuple[Privilege, ...] = ()
    sequence_privileges: tuple[Privilege, ...] = ()
    default_table_privileges: tuple[Privilege, ...] = ()
    default_sequence_privileges: tuple[Privilege, ...] = ()
    schema_privileges: tuple[Privilege, ...] = ()
    for_role: "Role | None" = None
    with_grant_option: bool = False

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
                Privilege.TRUNCATE,
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
                Privilege.TRUNCATE,
            ),
            default_sequence_privileges=(
                Privilege.USAGE,
                Privilege.SELECT,
                Privilege.UPDATE,
            ),
        )

    @staticmethod
    def get_default_read_privileges(role: Role) -> "RolePrivileges":
        """Get default read privileges for the role."""
        return RolePrivileges(
            role=role,
            table_privileges=(Privilege.SELECT,),
            sequence_privileges=(
                Privilege.USAGE,
                Privilege.SELECT,
            ),
            default_table_privileges=(Privilege.SELECT,),
            default_sequence_privileges=(
                Privilege.USAGE,
                Privilege.SELECT,
            ),
        )


@dataclasses.dataclass(frozen=True)
class SchemaConfig:
    """Schema configuration."""

    schema: Schema
    owner: Role = Role.OWNER
    role_privileges: tuple[RolePrivileges, ...] = ()


SCHEMA_CONFIGURATIONS = [
    SchemaConfig(
        schema=Schema.MANAGEMENT,
        role_privileges=(
            RolePrivileges.get_default_write_privileges(Role.WRITER),
            RolePrivileges.get_default_read_privileges(Role.READER),
            RolePrivileges.get_default_write_privileges(Role.PROCESSING_WORKER),
        ),
    ),
    SchemaConfig(
        schema=Schema.MIGRATIONS,
    ),
    SchemaConfig(
        schema=Schema.PROCESSING,
        role_privileges=(
            RolePrivileges(
                role=Role.PROCESSING_WORKER,
                table_privileges=(
                    Privilege.SELECT,
                    Privilege.INSERT,
                    Privilege.UPDATE,
                    Privilege.DELETE,
                    Privilege.TRUNCATE,
                ),
                sequence_privileges=(
                    Privilege.USAGE,
                    Privilege.SELECT,
                    Privilege.UPDATE,
                ),
                schema_privileges=(Privilege.USAGE, Privilege.CREATE),
            ),
            RolePrivileges(
                role=Role.OWNER,
                default_table_privileges=(
                    Privilege.SELECT,
                    Privilege.INSERT,
                    Privilege.UPDATE,
                    Privilege.DELETE,
                    Privilege.TRUNCATE,
                ),
                default_sequence_privileges=(
                    Privilege.USAGE,
                    Privilege.SELECT,
                    Privilege.UPDATE,
                ),
                for_role=Role.PROCESSING_WORKER,
                with_grant_option=True,
            ),
        ),
    ),
    SchemaConfig(
        schema=Schema.DEM,
        role_privileges=(
            RolePrivileges.get_default_write_privileges(Role.WRITER),
            RolePrivileges.get_default_read_privileges(Role.READER),
        ),
    ),
]
