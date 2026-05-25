# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import contextlib
import socket
import threading
import time
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    import fastapi


def unused_tcp_port() -> int:
    """Return a TCP port currently free on the loopback interface."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(
    check: Callable[[], bool],
    *,
    timeout: float = 10.0,
    interval: float = 0.05,
    message: str = "Condition not met in time",
) -> None:
    """Poll ``check`` until it returns truthy or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            if check():
                return
        time.sleep(interval)
    raise RuntimeError(message)


@contextlib.contextmanager
def serve_in_thread(
    app: fastapi.FastAPI,
    *,
    port: int | None = None,
    log_level: str = "warning",
) -> Iterator[str]:
    """Run ``app`` with uvicorn on a background thread.

    Yields the base URL. The server is signalled to exit on context teardown.
    """
    bound_port = port if port is not None else unused_tcp_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=bound_port,
        log_level=log_level,
        lifespan="on",
        ws="none",  # silence websocket deprecation warnings — we don't use them
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{bound_port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
