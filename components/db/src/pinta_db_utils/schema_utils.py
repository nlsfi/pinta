# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

from pinta_db.exceptions import MissingRoleError
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
    schema_config: "SchemaConfig",
    owner: str,
) -> list[str]:
    schema = schema_config.schema.value
    return [
        f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {owner}",
    ]


def _get_set_schema_role_privileges(
    schema_config: "SchemaConfig",
    role_config: "RolePrivileges",
    roles: dict[Role, str],
) -> list[str]:
    schema = schema_config.schema.value
    role = roles[role_config.role]
    for_role = roles[role_config.for_role or schema_config.owner]
    grant_option_suffix = " WITH GRANT OPTION" if role_config.with_grant_option else ""

    statements: list[str] = []

    if role_config.usage:
        statements.append(f"GRANT USAGE ON SCHEMA {schema} TO {role}")

    if role_config.table_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.table_privileges)} "
            f"ON ALL TABLES IN SCHEMA {schema} TO {role}{grant_option_suffix}"
        )

    if role_config.sequence_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.sequence_privileges)} "
            f"ON ALL SEQUENCES IN SCHEMA {schema} TO {role}{grant_option_suffix}"
        )

    if role_config.default_table_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{for_role} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_table_privileges)} "
            f"ON TABLES TO {role}{grant_option_suffix}"
        )

    if role_config.default_sequence_privileges:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE "
            f"{for_role} IN SCHEMA {schema} "
            f"GRANT {_grant_list(role_config.default_sequence_privileges)} "
            f"ON SEQUENCES TO {role}{grant_option_suffix}"
        )

    if role_config.schema_privileges:
        statements.append(
            f"GRANT {_grant_list(role_config.schema_privileges)} "
            f"ON SCHEMA {schema} TO {role}"
        )

    return statements


def get_set_schema_role_privileges_statements(
    schema_configuration: list["SchemaConfig"],
    roles: dict[Role, str],
) -> list[str]:
    """Ensure that the schemas and schema privileges are set up."""
    for role in Role:
        if role not in roles:
            raise MissingRoleError(role.name)

    statements: list[str] = []

    for schema_config in schema_configuration:
        statements.extend(
            _get_create_schema_statement(schema_config, roles[schema_config.owner])
        )

        for role_config in schema_config.role_privileges:
            statements.extend(
                _get_set_schema_role_privileges(
                    schema_config,
                    role_config,
                    roles,
                )
            )

    return statements
