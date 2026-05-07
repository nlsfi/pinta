# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Generate role/privilege diagrams and tables from databases."""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import dotenv
import sqlalchemy as sa

dotenv.load_dotenv()

from pinta_db_test_utils import db_utils  # noqa: E402
from pinta_db_utils import engine_utils  # noqa: E402

_PRIVILEGE_ORDER = (
    "USAGE",
    "CREATE",
    "CONNECT",
    "TEMPORARY",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)

_ROLE_ENV_SUFFIXES = ("_ROLE", "_USER")


@dataclass(frozen=True)
class DbTarget:
    """Database to introspect for a roles diagram."""

    label: str
    output_directory_name: str
    credentials: engine_utils.Credentials
    db_name: str
    role_names: tuple[str, ...]


@dataclass
class RoleInfo:
    """Single role's identity and login capability, as read from `pg_roles`."""

    name: str
    can_login: bool


@dataclass
class IntrospectionResult:
    """All catalog data needed to render a role/privilege diagram."""

    roles: list[RoleInfo] = field(default_factory=list)
    memberships: list[tuple[str, str]] = field(default_factory=list)
    db_privileges: dict[str, list[str]] = field(default_factory=dict)
    schema_privileges: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    default_privileges: dict[tuple[str, str, str], list[str]] = field(
        default_factory=dict
    )


def _role_names_for_prefix(prefix: str) -> tuple[str, ...]:
    """Return values of all env vars with the prefix."""
    return tuple(
        sorted(
            value
            for name, value in os.environ.items()
            if name.startswith(prefix)
            and any(name.endswith(suffix) for suffix in _ROLE_ENV_SUFFIXES)
        )
    )


def _role_diagram_targets() -> list[DbTarget]:
    primary_db_name = os.environ["DB_PRIMARY_NAME"]
    job_db_name = os.environ["DB_JOB_TEMPLATE_NAME"]
    return [
        DbTarget(
            label="Primary DB",
            output_directory_name="primary_db",
            credentials=db_utils.get_primary_admin_credentials(primary_db_name),
            db_name=primary_db_name,
            role_names=_role_names_for_prefix("DB_PRIMARY_"),
        ),
        DbTarget(
            label="Job DB",
            output_directory_name="job_db",
            credentials=db_utils.get_job_admin_credentials(job_db_name),
            db_name=job_db_name,
            role_names=_role_names_for_prefix("DB_JOB_"),
        ),
    ]


def build_role_diagram(target: DbTarget, out_dir: Path) -> Path:
    """Write a markdown role/privilege diagram for `target` and return the path."""
    engine = sa.create_engine(target.credentials.get_connection_string())
    try:
        with engine.connect() as conn:
            result = IntrospectionResult(
                roles=_fetch_roles(conn, target.role_names),
                memberships=_fetch_memberships(conn, target.role_names),
                db_privileges=_fetch_database_privileges(
                    conn, target.db_name, target.role_names
                ),
                schema_privileges=_fetch_schema_privileges(conn, target.role_names),
                default_privileges=_fetch_default_privileges(conn, target.role_names),
            )
    finally:
        engine.dispose()

    content = _render_markdown(target, result)
    output_dir = out_dir / target.output_directory_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "roles.md"

    original_content = output_file.read_text() if output_file.exists() else ""
    if content != original_content:
        output_file.write_text(content)
    return output_file


def _fetch_roles(conn: sa.Connection, role_names: tuple[str, ...]) -> list[RoleInfo]:
    rows = conn.execute(
        sa.text(
            "SELECT rolname AS name, rolcanlogin AS can_login "
            "FROM pg_roles "
            "WHERE rolname = ANY(:role_names) "
            "ORDER BY rolcanlogin, rolname"
        ),
        {"role_names": list(role_names)},
    ).all()
    return [RoleInfo(name=row.name, can_login=row.can_login) for row in rows]


def _fetch_memberships(
    conn: sa.Connection, role_names: tuple[str, ...]
) -> list[tuple[str, str]]:
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT member.rolname AS member, parent.rolname AS parent "
            "FROM pg_auth_members am "
            "JOIN pg_roles member ON member.oid = am.member "
            "JOIN pg_roles parent ON parent.oid = am.roleid "
            "WHERE member.rolname = ANY(:role_names) "
            "AND parent.rolname = ANY(:role_names) "
            "ORDER BY member.rolname, parent.rolname"
        ),
        {"role_names": list(role_names)},
    ).all()
    return [(row.member, row.parent) for row in rows]


def _fetch_database_privileges(
    conn: sa.Connection, db_name: str, role_names: tuple[str, ...]
) -> dict[str, list[str]]:
    rows = conn.execute(
        sa.text(
            "SELECT rolname AS name, "
            "       has_database_privilege(rolname, :db_name, 'CONNECT')   AS connect, "
            "       has_database_privilege(rolname, :db_name, 'TEMPORARY') AS temporary, "  # noqa: E501
            "       has_database_privilege(rolname, :db_name, 'CREATE')    AS create_privilege "  # noqa: E501
            "FROM pg_roles "
            "WHERE rolname = ANY(:role_names) "
            "ORDER BY rolname"
        ),
        {"db_name": db_name, "role_names": list(role_names)},
    ).all()
    out: dict[str, list[str]] = {}
    for row in rows:
        privileges = []
        if row.connect:
            privileges.append("CONNECT")
        if row.temporary:
            privileges.append("TEMPORARY")
        if row.create_privilege:
            privileges.append("CREATE")
        out[row.name] = privileges
    return out


def _fetch_schema_privileges(
    conn: sa.Connection, role_names: tuple[str, ...]
) -> dict[tuple[str, str], list[str]]:
    """Return mapping of (role, schema) -> direct schema privileges (USAGE/CREATE)."""
    rows = conn.execute(
        sa.text(
            "SELECT r.rolname AS role_name, n.nspname AS schema_name, "
            "       has_schema_privilege(r.rolname, n.nspname, 'USAGE')  AS usage, "
            "       has_schema_privilege(r.rolname, n.nspname, 'CREATE') AS create_privilege "  # noqa: E501
            "FROM pg_namespace n "
            "CROSS JOIN pg_roles r "
            "WHERE r.rolname = ANY(:role_names) "
            "AND n.nspname NOT IN ('pg_catalog', 'pg_toast', 'information_schema') "
            "AND n.nspname NOT LIKE 'pg_%' "
            "ORDER BY n.nspname, r.rolname"
        ),
        {"role_names": list(role_names)},
    ).all()
    out: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        privileges = []
        if row.usage:
            privileges.append("USAGE")
        if row.create_privilege:
            privileges.append("CREATE")
        if privileges:
            out[(row.role_name, row.schema_name)] = privileges
    return out


def _fetch_default_privileges(
    conn: sa.Connection, role_names: tuple[str, ...]
) -> dict[tuple[str, str, str], list[str]]:
    """Return (role, schema, owner) -> default table privileges."""
    rows = conn.execute(
        sa.text(
            "SELECT n.nspname AS schema_name, owner.rolname AS owner, "
            "       grantee.rolname AS grantee, a.privilege_type "
            "FROM pg_default_acl d "
            "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
            "JOIN pg_roles owner ON owner.oid = d.defaclrole "
            "CROSS JOIN LATERAL aclexplode(d.defaclacl) a "
            "JOIN pg_roles grantee ON grantee.oid = a.grantee "
            "WHERE d.defaclobjtype = 'r' "
            "AND grantee.rolname = ANY(:role_names) "
            "ORDER BY n.nspname, owner.rolname, grantee.rolname, a.privilege_type"
        ),
        {"role_names": list(role_names)},
    ).all()
    out: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        out[(row.grantee, row.schema_name, row.owner)].add(row.privilege_type)
    return {key: _sort_privileges(value) for key, value in out.items()}


def _sort_privileges(privileges: set[str]) -> list[str]:
    order = {name: i for i, name in enumerate(_PRIVILEGE_ORDER)}
    return sorted(privileges, key=lambda p: (order.get(p, len(order)), p))


def _render_membership_diagram(
    roles: list[RoleInfo], memberships: list[tuple[str, str]]
) -> list[str]:
    """Render the membership flowchart with subgraphs and noise filtered out."""
    login_roles = {role.name for role in roles if role.can_login}
    group_roles = [role for role in roles if not role.can_login]
    user_roles = [role for role in roles if role.can_login]

    filtered = [(m, p) for m, p in memberships if p not in login_roles]

    lines = ["## Membership", "", "```mermaid", "flowchart LR"]
    if group_roles:
        lines.append("    subgraph groups [Group roles]")
        lines.extend(f'        {role.name}[["{role.name}"]]' for role in group_roles)
        lines.append("    end")
    if user_roles:
        lines.append("    subgraph users [Login users]")
        lines.extend(f'        {role.name}(["{role.name}"])' for role in user_roles)
        lines.append("    end")
    lines.extend(f"    {member} --> {parent}" for member, parent in filtered)
    lines.append("```")
    lines.append("")
    return lines


def _render_markdown(target: DbTarget, result: IntrospectionResult) -> str:
    lines: list[str] = [f"# {target.label} roles & privileges", ""]

    lines.extend(_render_membership_diagram(result.roles, result.memberships))

    lines.append(f"## Database privileges (`{target.db_name}`)")
    lines.append("")
    lines.append("| Role | Privileges |")
    lines.append("| --- | --- |")
    for role in result.roles:
        privileges = result.db_privileges.get(role.name, [])
        lines.append(
            f"| `{role.name}` | {', '.join(privileges) if privileges else '—'} |"
        )
    lines.append("")

    lines.append("## Schema privileges")
    lines.append("")
    schemas = sorted({schema for _, schema in result.schema_privileges})
    if not schemas:
        lines.append("_No direct schema privileges found._")
    else:
        header = "| Role | " + " | ".join(f"`{schema}`" for schema in schemas) + " |"
        sep = "| --- |" + " --- |" * len(schemas)
        lines.append(header)
        lines.append(sep)
        for role in result.roles:
            cells = []
            for schema in schemas:
                privileges = result.schema_privileges.get((role.name, schema), [])
                cells.append(", ".join(privileges) if privileges else "—")
            lines.append(f"| `{role.name}` | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Default table privileges")
    lines.append("")
    if not result.default_privileges:
        lines.append("_No default table privileges found._")
    else:
        lines.append("| Grantee | Schema | Owner | Privileges |")
        lines.append("| --- | --- | --- | --- |")
        for (grantee, schema, owner), privileges in sorted(
            result.default_privileges.items()
        ):
            lines.append(
                f"| `{grantee}` | `{schema}` | `{owner}` | {', '.join(privileges)} |"
            )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    out_dir = Path(__file__).parent.parent / "docs"
    for target in _role_diagram_targets():
        build_role_diagram(target, out_dir)
