# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
from sqlmodel import SQLModel


class MissingFieldError(RuntimeError):
    def __init__(self, field_name: str) -> None:
        super().__init__(f"Field is missing from the model: {field_name}")


class MissingSchemaError(RuntimeError):
    def __init__(self, model: type[SQLModel]) -> None:
        super().__init__(f"Schema is missing from the model {model.__name__}")


class MissingRoleError(RuntimeError):
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Role is missing: {role_name}")


class PrivilegeChangeError(RuntimeError):
    def __init__(
        self,
        *,
        action: str,
        privileges: tuple[str, ...],
        schema: str,
        table: str,
        role: str,
    ) -> None:
        super().__init__(
            f"Failed to {action} {', '.join(privileges)} on "
            f"{schema}.{table} for role {role}. Either the session is not the "
            f"grantor of the privilege nor a member of the granting role, or "
            f"{role} holds the privilege through another role it is a member "
            f"of, which a REVOKE cannot take away."
        )
