# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import re
import typing
from typing import Any

import geoalchemy2.alembic_helpers

if typing.TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext


def render_item(
    obj_type: str,
    obj: Any,  # noqa: ANN401
    autogen_context: "AutogenContext",
) -> str | bool:
    """Alembic helper to render Geometry types.

    Uses geoalchemy2 for rendering and injects
    SRID from environment variable.
    """
    if not (
        rendered := geoalchemy2.alembic_helpers.render_item(
            obj_type, obj, autogen_context
        )
    ):
        # Default rendering for other objects
        return False

    # Ensure the SRID symbol is imported into the migration file
    autogen_context.imports.add("from pinta_db.env import SRID")

    # Replace srid=<number> with srid=SRID
    return re.sub(r"srid\s*=\s*[^,)\n]+", "srid=SRID", rendered)
