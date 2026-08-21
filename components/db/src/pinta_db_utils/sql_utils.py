# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import sqlalchemy as sa


def quote_identifier(bind: sa.Connection | sa.Engine, identifier: str) -> str:
    """Quote an SQL identifier for the bind's dialect."""
    return bind.dialect.identifier_preparer.quote(identifier)
