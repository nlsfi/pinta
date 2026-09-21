# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import json
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pinta_common import exceptions, feature_flag_registry, flags
from pinta_common.feature_flag_registry import FeatureFlag, FeatureFlagRegistry

FLAG_CONFIG_FILE = Path(__file__).parent / "data/feature_flags.json"

pytest_plugins = [
    "pinta_test_utils.fixtures.flags",
]


@pytest.fixture
def config_file(set_feature_flags: Callable[[dict[str, bool]], Path]) -> Path:
    return set_feature_flags({"FLAG_ON": True, "FLAG_OFF": False})


@pytest.fixture
def write_config(config_file: Path) -> Callable[[dict[str, bool]], None]:
    def _write(state: dict[str, bool]) -> None:
        content = {name: {"enabled": enabled} for name, enabled in state.items()}
        config_file.write_text(json.dumps(content), encoding="utf-8")

    return _write


@pytest.fixture
def registry(config_file: Path) -> FeatureFlagRegistry:
    registry = feature_flag_registry._registry
    assert registry is not None
    assert registry._config_file == config_file
    return registry


def test_feature_flag_json_matches_declared_flags():
    declared = {
        flag.name for flag in vars(flags).values() if isinstance(flag, FeatureFlag)
    }
    configured = set(json.loads(FLAG_CONFIG_FILE.read_text(encoding="utf-8")))

    assert configured == declared


@pytest.mark.usefixtures("registry")
def test_flag_state_is_read_from_config_file():
    flag_on = FeatureFlag(name="FLAG_ON", description="on")
    flag_off = FeatureFlag(name="FLAG_OFF", description="off")

    assert flag_on.enabled
    assert flag_on
    assert not flag_off.enabled
    assert not flag_off


@pytest.mark.usefixtures("registry")
def test_flag_state_is_reloaded_when_cache_is_disabled(
    write_config: Callable[[dict[str, bool]], None],
):
    flag = FeatureFlag(name="FLAG_ON", description="on")
    assert flag

    write_config({"FLAG_ON": False, "FLAG_OFF": False})

    assert not flag


def test_flag_state_is_reloaded_after_ttl(
    registry: FeatureFlagRegistry,
    write_config: Callable[[dict[str, bool]], None],
    monkeypatch: pytest.MonkeyPatch,
):
    registry._ttl = 10
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    flag = FeatureFlag(name="FLAG_ON", description="on")
    assert flag

    write_config({"FLAG_ON": False, "FLAG_OFF": False})
    monkeypatch.setattr(time, "monotonic", lambda: 5.0)
    assert flag

    monkeypatch.setattr(time, "monotonic", lambda: 10.0)
    assert not flag


def test_unregistered_flag_state_raises(registry: FeatureFlagRegistry):
    with pytest.raises(exceptions.MissingFeatureFlagError):
        registry.flag_state("FLAG_UNKNOWN")


@pytest.mark.usefixtures("registry")
def test_declaring_flag_missing_from_config_file_raises():
    with pytest.raises(exceptions.MissingFeatureFlagError) as excinfo:
        FeatureFlag(name="FLAG_UNKNOWN", description="not in the config file")

    assert excinfo.value.names == ["FLAG_UNKNOWN"]


@pytest.mark.usefixtures("registry")
def test_flag_removed_from_config_file_raises_on_reload(
    write_config: Callable[[dict[str, bool]], None],
):
    flag = FeatureFlag(name="FLAG_ON", description="on")
    write_config({"FLAG_OFF": False})

    with pytest.raises(exceptions.MissingFeatureFlagError):
        flag.enabled  # noqa: B018


@pytest.mark.usefixtures("registry")
@pytest.mark.parametrize(
    "content", ["not json", '{"FLAG_ON": true}', '{"FLAG_ON": {"enabled": "yes"}}']
)
def test_malformed_config_file_raises(config_file: Path, content: str):
    config_file.write_text(content, encoding="utf-8")

    with pytest.raises(exceptions.FeatureFlagConfigError):
        FeatureFlag(name="FLAG_ON", description="on")


def test_missing_config_file_raises(tmp_path: Path):
    with pytest.raises(exceptions.FeatureFlagConfigError):
        FeatureFlagRegistry(tmp_path / "missing.json")


@pytest.mark.usefixtures("registry")
def test_declaring_flag_twice_with_different_description_raises():
    FeatureFlag(name="FLAG_ON", description="on")

    with pytest.raises(exceptions.FeatureFlagDefinitionError):
        FeatureFlag(name="FLAG_ON", description="something else")


@pytest.mark.parametrize(
    ("name", "description"), [("", "description"), ("FLAG_ON", " ")]
)
def test_flag_without_name_or_description_raises(name: str, description: str):
    with pytest.raises(exceptions.FeatureFlagDefinitionError):
        FeatureFlag(name=name, description=description)


def test_all_flags_are_enabled_in_development_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(feature_flag_registry, "_registry", None)

    assert FeatureFlag(name="FLAG_UNKNOWN", description="not in any config file")


def test_no_registry_is_created_in_development_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PINTA_DEVELOPMENT_MODE", "true")
    monkeypatch.delenv("PINTA_FEATURE_FLAG_CONFIG", raising=False)

    assert feature_flag_registry._create_registry() is None


def test_registry_is_created_from_settings(
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PINTA_DEVELOPMENT_MODE", "false")
    monkeypatch.setenv("PINTA_FEATURE_FLAG_CONFIG", str(config_file))

    registry = feature_flag_registry._create_registry()

    assert registry is not None
    assert registry._config_file == config_file


@pytest.mark.usefixtures("registry")
def test_clear_cache_forces_reload(
    registry: FeatureFlagRegistry,
    write_config: Callable[[dict[str, bool]], None],
    monkeypatch: pytest.MonkeyPatch,
):
    registry._ttl = 10
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    flag = FeatureFlag(name="FLAG_ON", description="on")
    assert flag

    write_config({"FLAG_ON": False, "FLAG_OFF": False})
    assert flag

    feature_flag_registry.clear_cache()
    assert not flag


@pytest.mark.usefixtures("registry")
def test_flag_str_shows_name_and_state():
    flag = FeatureFlag(name="FLAG_OFF", description="off")

    assert str(flag) == "FLAG_OFF - enabled: False"


def test_missing_config_setting_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PINTA_DEVELOPMENT_MODE", "false")
    monkeypatch.delenv("PINTA_FEATURE_FLAG_CONFIG", raising=False)

    with pytest.raises(exceptions.MissingEnvironmentError):
        feature_flag_registry._create_registry()
