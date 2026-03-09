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
