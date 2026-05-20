# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import logging
import os
from collections.abc import AsyncGenerator

import fastapi

import pinta_backend
from pinta_backend import middlewares, routes, utils


def setup_uvicorn_loggers() -> None:
    """Add asctime to all uvicorn default logger handlers."""
    for logger_name in logging.root.manager.loggerDict:
        if not logger_name.startswith("uvicorn"):
            continue
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )


@contextlib.asynccontextmanager
async def application_lifespan(
    app: fastapi.FastAPI,  # noqa: ARG001
) -> AsyncGenerator[None, None]:
    """Configure loggers & open the pool on app startup.

    Also initialize database config and start the background processing
    thread for the queued tasks.
    """
    utils.setup_default_logger_handlers()
    setup_uvicorn_loggers()
    pinta_backend.LOGGER.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    yield


api = fastapi.FastAPI(
    title="Pinta backend",
    lifespan=application_lifespan,
)


middlewares.register(api)
api.include_router(routes.router)
