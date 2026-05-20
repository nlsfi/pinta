# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Awaitable, Callable

import fastapi
from starlette.responses import Response

from pinta_backend import i18n


async def language_middleware(
    request: fastapi.Request,
    call_next: Callable[[fastapi.Request], Awaitable[Response]],
) -> Response:
    """Set the active request language from the Accept-Language header.

    The middleware extracts the preferred language from the incoming
    ``Accept-Language`` header, stores it in the i18n context, and
    exposes the selected language through the ``Content-Language``
    response header.

    Example header:
        fi-FI,fi;q=0.9,en;q=0.8
    """
    accept_language = request.headers.get("Accept-Language", "en")

    try:
        language = accept_language.split(",")[0].split("-")[0]
    except IndexError:
        language = "en"

    i18n.set_language(language)

    response = await call_next(request)

    response.headers["Content-Language"] = i18n.get_language()

    return response


def register(app: fastapi.FastAPI) -> None:
    """Register application middlewares."""
    app.middleware("http")(language_middleware)
