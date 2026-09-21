# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import json
import pathlib
from collections.abc import Callable, Iterator

import pytest
from pinta_common import feature_flag_registry


@pytest.fixture(autouse=True)
def _isolate_feature_flag_registry() -> Iterator[None]:
    """Fail the test if it leaves a registry behind for the next one."""
    registry_before = feature_flag_registry._registry
    yield
    feature_flag_registry.clear_cache()
    assert feature_flag_registry._registry is registry_before, (
        "feature flag registry leaked from the test"
    )


@pytest.fixture
def set_feature_flags(
    monkeypatch: "pytest.MonkeyPatch", tmp_path: pathlib.Path
) -> Callable[[dict[str, bool]], pathlib.Path]:
    """Write a flag config file and point the registry at it for this test."""

    def _set_feature_flags(flag_values: dict[str, bool]) -> pathlib.Path:
        config_file = tmp_path / "feature_flags.json"
        content = {name: {"enabled": enabled} for name, enabled in flag_values.items()}
        config_file.write_text(json.dumps(content), encoding="utf-8")
        registry = feature_flag_registry.FeatureFlagRegistry(config_file, ttl=0)
        monkeypatch.setattr(feature_flag_registry, "_registry", registry)
        return config_file

    return _set_feature_flags
