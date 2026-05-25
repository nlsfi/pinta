# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import logging

from pinta_backend import settings

LOGGER = logging.getLogger(__name__)


def run_development_app() -> None:  # pragma: no cover  # noqa: D103
    import uvicorn  # noqa: PLC0415

    app_settings = settings.get_settings()
    uvicorn.run(
        "pinta_backend.app:api",
        host=app_settings.api_host,
        port=app_settings.api_port,
        reload=True,
    )


if __name__ == "__main__":  # pragma: no cover
    run_development_app()
