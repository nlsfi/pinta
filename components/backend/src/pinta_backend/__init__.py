# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging

LOGGER = logging.getLogger(__name__)


def run_development_app() -> None:  # pragma: no cover  # noqa: D103
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        "pinta_backend.app:api",
        host="localhost",
        port=3011,
        reload=True,
    )


if __name__ == "__main__":  # pragma: no cover
    run_development_app()
