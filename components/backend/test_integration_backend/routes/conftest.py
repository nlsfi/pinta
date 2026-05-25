# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterator

import httpx
import pytest

from pinta_backend_test_utils import (
    STUB_AIRFLOW_PASSWORD,
    STUB_AIRFLOW_USERNAME,
    StubAirflowState,
    build_stub_airflow,
    serve_in_thread,
    wait_until,
)


@pytest.fixture(scope="module")
def stub_airflow() -> Iterator[tuple[str, StubAirflowState]]:
    app_stub, state = build_stub_airflow()
    with serve_in_thread(app_stub) as base_url:
        wait_until(
            lambda: httpx.get(f"{base_url}/docs", timeout=0.5).status_code < 500,
            timeout=10.0,
            message=f"Stub Airflow at {base_url} did not become ready",
        )
        yield base_url, state


@pytest.fixture
def backend_with_stub_airflow(
    stub_airflow: tuple[str, StubAirflowState],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    stub_url, _ = stub_airflow

    monkeypatch.setenv("AIRFLOW_BASE_URL", stub_url)
    monkeypatch.setenv("AIRFLOW_USERNAME", STUB_AIRFLOW_USERNAME)
    monkeypatch.setenv("AIRFLOW_PASSWORD", STUB_AIRFLOW_PASSWORD)

    from pinta_backend import airflow_client, app, settings

    def _clear_caches() -> None:
        settings.get_settings.cache_clear()
        airflow_client.get_airflow_client.cache_clear()

    _clear_caches()
    try:
        with serve_in_thread(app.api) as base_url:
            wait_until(
                lambda: httpx.get(f"{base_url}/health", timeout=1.0).status_code == 200,
                timeout=10.0,
                message="pinta backend did not become healthy",
            )
            yield base_url
    finally:
        _clear_caches()
