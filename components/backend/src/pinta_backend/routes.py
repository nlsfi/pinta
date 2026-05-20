# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import fastapi

from pinta_backend import models
from pinta_backend.i18n import _, get_language

router = fastapi.APIRouter(tags=["default"])


@router.get("/health")
async def get_health() -> models.ApiHealth:
    """Return app health status."""
    return models.ApiHealth(parsed_language=get_language())


@router.get("/hello-world", tags=["default"])
async def get_foo() -> dict[str, str]:
    """Return app health status."""
    return {"message": _("Hello World")}
