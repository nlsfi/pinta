# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

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
    role_mapping: "dict[Role, str]",
) -> list[str]:
    schema = schema_config.schema.value
    role = role_mapping[role_config.role]

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


def get_set_schema_role_privileges_statements(
    schema_configuration: list["SchemaConfig"],
    owner_role: str,
    role_mapping: "dict[Role, str]",
) -> list[str]:
    """Ensure that the schemas and schema privileges are set up."""
    missing = set(Role) - set(role_mapping)
    if missing:
        msg = f"Missing role mappings for: {missing}"
        raise ValueError(msg)

    statements: list[str] = []

    for schema_config in schema_configuration:
        owner_roles = (owner_role, *schema_config.extra_schema_owners)
        statements.extend(_get_create_schema_statement(schema_config, owner_roles))

        for role_config in schema_config.role_privileges:
            statements.extend(
                _get_set_schema_role_privileges(
                    schema_config,
                    role_config,
                    owner_role=owner_role,
                    role_mapping=role_mapping,
                )
            )

    return statements
