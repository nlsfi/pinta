# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import requests
import uvicorn
from pinta_backend_test_utils import live_server

if TYPE_CHECKING:
    from collections.abc import Generator

DAGS_FOLDER = Path(__file__).parents[2] / "dags" / "src" / "pinta_dags" / "dags"
AIRFLOW_BOOT_TIMEOUT_S = 60.0
BACKEND_BOOT_TIMEOUT_S = 30.0
# Airflow boot is slow; poll at 1s to avoid log spam during the long wait.
AIRFLOW_POLL_INTERVAL_S = 1.0
HELLO_WORLD_TAG = "hello_world"


def _build_standalone_env(home: Path, api_port: int) -> dict[str, str]:
    env = os.environ.copy()
    env["AIRFLOW_HOME"] = str(home)
    env["AIRFLOW__CORE__DAGS_FOLDER"] = str(DAGS_FOLDER)
    env["AIRFLOW__CORE__LOAD_EXAMPLES"] = "false"
    env["AIRFLOW__API__PORT"] = str(api_port)
    env["AIRFLOW__API__HOST"] = "127.0.0.1"
    # Default [dag_processor] refresh_interval is 5 minutes — too slow for
    # an E2E test that needs the bundled DAGs visible quickly.
    env["AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL"] = "5"
    env.pop("AIRFLOW__CORE__EXECUTOR", None)
    return env


def _terminate_process_group(proc: subprocess.Popen) -> None:
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


def _fetch_admin_token(base_url: str, password: str) -> str:
    response = requests.post(
        f"{base_url}/auth/token",
        json={"username": "admin", "password": password},
        timeout=5.0,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("access_token")


@pytest.fixture(scope="module")
def airflow_standalone() -> Generator[tuple[str, str], None, None]:
    """Launch `airflow standalone` in a temporary AIRFLOW_HOME.

    Yields the API base URL and the auto-generated admin password.
    """
    if shutil.which("airflow") is None:
        pytest.skip("airflow CLI not available")

    api_port = live_server.unused_tcp_port()
    home = Path(tempfile.mkdtemp(prefix="pinta-e2e-airflow-"))
    base_url = f"http://127.0.0.1:{api_port}"
    password_file = home / "simple_auth_manager_passwords.json.generated"
    log_file = home / "standalone.log"
    log_handle = log_file.open("wb")

    proc = subprocess.Popen(
        ["airflow", "standalone"],
        env=_build_standalone_env(home, api_port),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    def _skip_with_log(message: str) -> None:
        _terminate_process_group(proc)
        log_handle.close()
        tail = log_file.read_text(errors="replace")[-4000:] if log_file.exists() else ""
        shutil.rmtree(home, ignore_errors=True)
        pytest.skip(f"{message}\n--- airflow standalone log tail ---\n{tail}")

    def _api_and_password_ready() -> bool:
        if proc.poll() is not None:
            msg = f"airflow standalone exited with code {proc.returncode}"
            raise RuntimeError(msg)
        if not password_file.exists():
            return False
        return requests.get(f"{base_url}/api/v2/version", timeout=2.0).status_code in (
            200,
            401,
        )

    try:
        live_server.wait_until(
            _api_and_password_ready,
            timeout=AIRFLOW_BOOT_TIMEOUT_S,
            interval=AIRFLOW_POLL_INTERVAL_S,
            message="airflow standalone did not become ready in time",
        )
    except RuntimeError as exc:
        _skip_with_log(str(exc))

    admin_password = json.loads(password_file.read_text())["admin"]

    def _dag_visible() -> bool:
        token = _fetch_admin_token(base_url, admin_password)
        dags = requests.get(
            f"{base_url}/api/v2/dags",
            headers={"Authorization": f"Bearer {token}"},
            params={"tags": HELLO_WORLD_TAG, "tags_match_mode": "any"},
            timeout=5.0,
        )
        dags.raise_for_status()
        return dags.json().get("total_entries", 0) > 0

    try:
        live_server.wait_until(
            _dag_visible,
            timeout=AIRFLOW_BOOT_TIMEOUT_S,
            interval=AIRFLOW_POLL_INTERVAL_S,
            message=f"DAG with tag '{HELLO_WORLD_TAG}' was not parsed in time",
        )
    except RuntimeError as exc:
        _skip_with_log(str(exc))

    try:
        yield base_url, admin_password
    finally:
        with contextlib.suppress(Exception):
            _terminate_process_group(proc)
        log_handle.close()
        shutil.rmtree(home, ignore_errors=True)


@pytest.fixture
def backend_server(
    airflow_standalone: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[str, None, None]:
    airflow_url, admin_password = airflow_standalone

    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_BASE_URL", airflow_url)
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_USERNAME", "admin")
    monkeypatch.setenv("PINTA_BACKEND_AIRFLOW_PASSWORD", admin_password)

    from pinta_backend import airflow_client, app, settings  # noqa: PLC0415

    settings.get_settings.cache_clear()
    airflow_client.get_airflow_client.cache_clear()

    port = live_server.unused_tcp_port()
    config = uvicorn.Config(
        app.api, host="127.0.0.1", port=port, log_level="warning", ws="none"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        live_server.wait_until(
            lambda: requests.get(f"{base_url}/health", timeout=1.0).status_code == 200,
            timeout=BACKEND_BOOT_TIMEOUT_S,
            message="pinta backend did not become healthy",
        )
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        settings.get_settings.cache_clear()
        airflow_client.get_airflow_client.cache_clear()


def test_workflow_endpoint_triggers_real_airflow_dag(backend_server: str) -> None:
    response = requests.post(
        f"{backend_server}/workflows/{HELLO_WORLD_TAG}",
        json={"parameters": {"name": "Pinta"}},
        headers={"Accept-Language": "en"},
        timeout=30,
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["dag_id"] == "print_hello_world"
    assert body["dag_run_id"].startswith("manual__")
    assert body["message"] == "Workflow run started."


def test_workflow_endpoint_rejects_invalid_parameters(backend_server: str) -> None:
    # name should be string
    response = requests.post(
        f"{backend_server}/workflows/{HELLO_WORLD_TAG}",
        json={"parameters": {"name": 42}},
        headers={"Accept-Language": "en"},
        timeout=30,
    )

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail.startswith("Invalid workflow parameters:")
    assert "name" in detail
