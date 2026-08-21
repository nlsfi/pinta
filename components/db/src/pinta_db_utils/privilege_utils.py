# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import sqlalchemy as sa
import sqlmodel

from pinta_db import exceptions
from pinta_db_utils import sql_utils

TABLE_PRIVILEGES = frozenset(
    {"SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"}
)


def _validate_privileges(privileges: tuple[str, ...]) -> str:
    if not privileges:
        msg = "At least one privilege is required"
        raise ValueError(msg)
    if unknown := sorted(set(privileges) - TABLE_PRIVILEGES):
        msg = f"Unsupported table privileges: {', '.join(unknown)}"
        raise ValueError(msg)
    return ", ".join(privileges)


def _ensure_role_exists(session: sqlmodel.Session, role: str) -> None:
    exists = session.exec(  # type: ignore[call-overload]
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role").bindparams(role=role)
    ).first()
    if exists is None:
        raise exceptions.MissingRoleError(role)


def _qualified_table(session: sqlmodel.Session, schema: str, table: str) -> str:
    bind = session.get_bind()
    quoted_schema = sql_utils.quote_identifier(bind, schema)
    quoted_table = sql_utils.quote_identifier(bind, table)
    return f"{quoted_schema}.{quoted_table}"


def _has_table_privilege(
    session: sqlmodel.Session, qualified_table: str, role: str, privilege: str
) -> bool:
    result = session.exec(  # type: ignore[call-overload]
        sa.text("SELECT has_table_privilege(:role, :table, :privilege)").bindparams(
            role=role, table=qualified_table, privilege=privilege
        )
    ).first()
    return bool(result and result[0])


def role_has_all_table_privileges(
    session: sqlmodel.Session,
    schema: str,
    table: str,
    role: str,
    privileges: tuple[str, ...],
) -> bool:
    """Return whether ``role`` holds every one of ``privileges`` on the table."""
    _validate_privileges(privileges)
    qualified_table = _qualified_table(session, schema, table)
    return all(
        _has_table_privilege(session, qualified_table, role, privilege)
        for privilege in privileges
    )


def role_has_any_table_privilege(
    session: sqlmodel.Session,
    schema: str,
    table: str,
    role: str,
    privileges: tuple[str, ...],
) -> bool:
    """Return whether ``role`` still holds any of ``privileges`` on the table."""
    _validate_privileges(privileges)
    qualified_table = _qualified_table(session, schema, table)
    return any(
        _has_table_privilege(session, qualified_table, role, privilege)
        for privilege in privileges
    )


def grant_table_privileges(
    session: sqlmodel.Session,
    schema: str,
    table: str,
    role: str,
    privileges: tuple[str, ...],
) -> None:
    """Grant ``privileges`` on a table to ``role`` and commit the change."""
    privileges_str = _validate_privileges(privileges)
    _ensure_role_exists(session, role)

    session.exec(  # type: ignore[call-overload]
        sa.text(
            f"GRANT {privileges_str} "
            f"ON TABLE {_qualified_table(session, schema, table)} "
            f"TO {sql_utils.quote_identifier(session.get_bind(), role)}"
        )
    )
    session.commit()

    if not role_has_all_table_privileges(session, schema, table, role, privileges):
        raise exceptions.PrivilegeChangeError(
            action="grant",
            privileges=privileges,
            schema=schema,
            table=table,
            role=role,
        )


def revoke_table_privileges(
    session: sqlmodel.Session,
    schema: str,
    table: str,
    role: str,
    privileges: tuple[str, ...],
) -> None:
    """Revoke ``privileges`` on a table from ``role`` and commit the change."""
    privileges_str = _validate_privileges(privileges)
    _ensure_role_exists(session, role)

    session.exec(  # type: ignore[call-overload]
        sa.text(
            f"REVOKE {privileges_str} "
            f"ON TABLE {_qualified_table(session, schema, table)} "
            f"FROM {sql_utils.quote_identifier(session.get_bind(), role)}"
        )
    )
    session.commit()

    if role_has_any_table_privilege(session, schema, table, role, privileges):
        raise exceptions.PrivilegeChangeError(
            action="revoke",
            privileges=privileges,
            schema=schema,
            table=table,
            role=role,
        )
