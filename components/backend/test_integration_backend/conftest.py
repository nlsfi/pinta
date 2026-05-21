# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

# tests/conftest.py
import socket
import threading
import time
from collections.abc import Generator

import httpx
import pytest
import uvicorn

from pinta_backend import app


def unused_tcp_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def worker_name(worker_id: str) -> str:
    return worker_id


@pytest.fixture(scope="session")
def live_server() -> Generator[str, None, None]:
    port = unused_tcp_port()
    config = uvicorn.Config(
        app.api,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
        ws="none",  # supress deprecation warnings, websocket not used
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    timeout = time.time() + 10
    while time.time() < timeout:
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code < 500:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        msg = "Live test server failed to start"
        raise RuntimeError(msg)

    yield base_url

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def api(live_server: str) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=live_server, timeout=10.0) as client:
        yield client
