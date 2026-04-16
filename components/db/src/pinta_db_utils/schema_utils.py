# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

from pinta_db.exceptions import MissingRoleError
from pinta_db.main_db.models.all import *  # noqa: F403
from pinta_db.schemas import (
    DelegatedAccess,
    Privilege,
    Role,
    SchemaAccess,
    SchemaConfig,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable


def _grant_list(privileges: "Iterable[Privilege]") -> str:
    return ", ".join(x.name for x in privileges)


def _get_create_schema_statement(
    schema_config: "SchemaConfig",
    owner: str,
) -> str:
    return (
        f"CREATE SCHEMA IF NOT EXISTS {schema_config.schema.value} "
        f"AUTHORIZATION {owner}"
    )


def _statements_for_access(
    schema_config: "SchemaConfig",
    access: "SchemaAccess",
    roles: dict[Role, str],
) -> list[str]:
    schema = schema_config.schema.value
    role = roles[access.role]
    owner = roles[schema_config.owner]
    privileges = access.level.privileges

    statements = [
        f"GRANT {_grant_list((Privilege.USAGE, *privileges.schema_extra))} "
        f"ON SCHEMA {schema} TO {role}"
    ]

    if privileges.tables:
        statements.append(
            f"GRANT {_grant_list(privileges.tables)} "
            f"ON ALL TABLES IN SCHEMA {schema} TO {role}"
        )
    if privileges.sequences:
        statements.append(
            f"GRANT {_grant_list(privileges.sequences)} "
            f"ON ALL SEQUENCES IN SCHEMA {schema} TO {role}"
        )
    if privileges.tables:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA {schema} "
            f"GRANT {_grant_list(privileges.tables)} ON TABLES TO {role}"
        )
    if privileges.sequences:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA {schema} "
            f"GRANT {_grant_list(privileges.sequences)} ON SEQUENCES TO {role}"
        )

    return statements


def _statements_for_delegation(
    schema_config: "SchemaConfig",
    delegated: "DelegatedAccess",
    roles: dict[Role, str],
) -> list[str]:
    schema = schema_config.schema.value
    creator = roles[delegated.creator]
    grantee = roles[delegated.grantee]
    privileges = delegated.level.privileges
    grant_option = " WITH GRANT OPTION" if delegated.with_grant_option else ""

    statements: list[str] = []

    if privileges.tables:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {creator} IN SCHEMA {schema} "
            f"GRANT {_grant_list(privileges.tables)} "
            f"ON TABLES TO {grantee}{grant_option}"
        )
    if privileges.sequences:
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {creator} IN SCHEMA {schema} "
            f"GRANT {_grant_list(privileges.sequences)} "
            f"ON SEQUENCES TO {grantee}{grant_option}"
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
        statements.append(
            _get_create_schema_statement(schema_config, roles[schema_config.owner])
        )
        for access in schema_config.access:
            statements.extend(_statements_for_access(schema_config, access, roles))
        for delegated in schema_config.delegated:
            statements.extend(
                _statements_for_delegation(schema_config, delegated, roles)
            )

    return statements
