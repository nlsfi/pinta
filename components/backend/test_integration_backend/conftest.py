# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterator

import httpx
import pytest

from pinta_backend import app
from pinta_backend_test_utils import serve_in_thread, wait_until


@pytest.fixture(scope="session")
def worker_name(worker_id: str) -> str:
    return worker_id


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    with serve_in_thread(app.api) as base_url:
        wait_until(
            lambda: httpx.get(f"{base_url}/health", timeout=0.5).status_code < 500,
            timeout=10.0,
            message=f"Live test server at {base_url} did not become healthy",
        )
        yield base_url


@pytest.fixture
def api(live_server: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=live_server, timeout=10.0) as client:
        yield client
