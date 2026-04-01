# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

from pydantic.dataclasses import dataclass

from pinta_db.models.all import *  # noqa: F403
from pinta_db.schemas import (
    Privilege,
    Role,
    RolePrivileges,
    SchemaConfig,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable


def _grant_list(privileges: "Iterable[Privilege]") -> str:
    return ", ".join(x.name for x in privileges)


def _get_create_schema_statement(
    schema_config: "SchemaConfig", owner_roles: tuple[str, ...]
) -> list[str]:
    schema = schema_config.schema.value
    return [
        f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {owner_roles[0]}",
        f"GRANT {_grant_list(schema_config.owner_privileges)} "
        f"ON SCHEMA {schema} TO {','.join(owner_roles)}",
    ]


def _get_set_schema_role_privileges(
    schema_config: "SchemaConfig",
    role_config: "RolePrivileges",
    *,
    owner_role: str,
    writer_role: str,
    reader_role: str,
) -> list[str]:
    schema = schema_config.schema.value
    if role_config.role == Role.WRITER:
        role = writer_role
    elif role_config.role == Role.READER:
        role = reader_role
    elif role_config.role == Role.PROCESSING_WORKER:
        role = writer_role  # Processing worker has same privileges as writer
    else:
        raise ValueError(role_config.role)

    statements: list[str] = []

    if role_config.usage:
        statements.append(f"GRANT USAGE ON SCHEMA {schema} TO {role}")

    if role_config.table_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.table_privileges)} "
            f"ON ALL TABLES IN SCHEMA {schema} TO {role}"
        )

    if role_config.sequence_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.sequence_privileges)} "
            f"ON ALL SEQUENCES IN SCHEMA {schema} TO {role}"
        )

    if role_config.default_table_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{owner_role} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_table_privileges)} "
            f"ON TABLES TO {role}"
        )

    if role_config.default_sequence_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{owner_role} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_sequence_privileges)} "
            f"ON SEQUENCES TO {role}"
        )

    return statements


@dataclass
class Roles:
    """Mandatory roles for the database."""

    owner: str
    writer: str
    reader: str


def get_set_schema_role_privileges_statements(
    schema_configuration: list["SchemaConfig"],
    roles: Roles,
) -> list[str]:
    """Ensure that the schemas and schema privileges are set up."""
    statements: list[str] = []

    for schema_config in schema_configuration:
        owner_roles = (roles.owner, *schema_config.extra_schema_owners)
        statements.extend(_get_create_schema_statement(schema_config, owner_roles))

        for role_config in schema_config.role_privileges:
            statements.extend(
                _get_set_schema_role_privileges(
                    schema_config,
                    role_config,
                    owner_role=roles.owner,
                    writer_role=roles.writer,
                    reader_role=roles.reader,
                )
            )

    return statements
