# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import importlib
from collections.abc import Iterator

import pytest

from pinta_dags import config


@pytest.fixture
def reload_config() -> Iterator[None]:
    """Re-import config so module-level Variable lookups see patched env."""
    yield
    importlib.reload(config)


@pytest.mark.parametrize("development_mode", ["true", "false"])
def test_development_mode_is_forwarded_to_container_tasks(
    monkeypatch: pytest.MonkeyPatch, reload_config: None, development_mode: str
) -> None:
    monkeypatch.setenv("PINTA_DEVELOPMENT_MODE", development_mode)
    importlib.reload(config)

    environment = config.PINTA_CONTAINER_TASK_ARGS["environment"]

    assert environment["PINTA_DEVELOPMENT_MODE"] == development_mode


def test_feature_flag_config_is_mounted_to_container_tasks(
    monkeypatch: pytest.MonkeyPatch, reload_config: None
) -> None:
    monkeypatch.setenv(
        "AIRFLOW_VAR_PINTA_FEATURE_FLAG_CONFIG_PATH", "/host/feature_flags.json"
    )
    importlib.reload(config)

    environment = config.PINTA_CONTAINER_TASK_ARGS["environment"]
    mounts = {m["Target"]: m for m in config.PINTA_CONTAINER_TASK_ARGS["mounts"]}

    assert environment["PINTA_FEATURE_FLAG_CONFIG"] == "/feature_flags.json"
    assert mounts["/feature_flags.json"]["Source"] == "/host/feature_flags.json"
    assert mounts["/feature_flags.json"]["ReadOnly"] is True


def test_feature_flag_config_is_absent_without_variable(
    monkeypatch: pytest.MonkeyPatch, reload_config: None
) -> None:
    monkeypatch.delenv("AIRFLOW_VAR_PINTA_FEATURE_FLAG_CONFIG_PATH", raising=False)
    importlib.reload(config)

    environment = config.PINTA_CONTAINER_TASK_ARGS["environment"]
    targets = [m["Target"] for m in config.PINTA_CONTAINER_TASK_ARGS["mounts"]]

    assert "PINTA_FEATURE_FLAG_CONFIG" not in environment
    assert "/feature_flags.json" not in targets
