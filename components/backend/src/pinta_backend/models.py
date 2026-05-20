# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from importlib import metadata

import pydantic


class ApiHealth(pydantic.BaseModel):
    """Api health response."""

    backend_version: str = metadata.version("pinta_backend")
    parsed_language: str
