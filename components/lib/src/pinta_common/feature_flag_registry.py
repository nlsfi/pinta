# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pinta_common import exceptions, settings

LOGGER = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 5.0


class FeatureFlagRegistry:
    """Declared flags and their states, re-read from the config file every ttl."""

    def __init__(self, config_file: Path, ttl: float = DEFAULT_TTL_SECONDS) -> None:
        if not config_file.exists():
            raise exceptions.FeatureFlagConfigError(config_file, "file not found")
        self._config_file = config_file
        self._ttl = ttl
        self._flags: dict[str, FeatureFlag] = {}

    def flag(self, name: str) -> "FeatureFlag | None":
        """Return the declared flag with the given name."""
        return self._flags.get(name)

    def add(self, feature_flag: "FeatureFlag") -> None:
        """Declare a flag, raising if the config file does not contain it."""
        self._state(feature_flag.name)
        self._flags[feature_flag.name] = feature_flag

    def flag_state(self, name: str) -> bool:
        """Return the current state of the flag from the config file."""
        return self._state(name)[name]

    def _state(self, *extra_names: str) -> dict[str, bool]:
        bucket = (
            int(time.monotonic() // self._ttl) if self._ttl > 0 else time.monotonic_ns()
        )
        names = tuple(sorted((*self._flags, *extra_names)))
        return _load_state(self._config_file, bucket, names)


def clear_cache() -> None:
    """Force a re-read of the config file on the next state lookup."""
    _load_state.cache_clear()


@lru_cache(maxsize=1)
def _load_state(
    config_file: Path, _bucket: int, names: tuple[str, ...]
) -> dict[str, bool]:
    """Read the config file and check that it contains every name."""
    LOGGER.debug("Reading feature flags from %s", config_file)
    try:
        content = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise exceptions.FeatureFlagConfigError(config_file, str(e)) from e

    state: dict[str, bool] = {}
    for name, entry in content.items():
        enabled = entry.get("enabled") if isinstance(entry, dict) else None
        if not isinstance(enabled, bool):
            raise exceptions.FeatureFlagConfigError(
                config_file, f'"{name}" must have a boolean "enabled" value'
            )
        state[name] = enabled

    missing = set(names) - state.keys()
    if missing:
        raise exceptions.MissingFeatureFlagError(config_file, missing)
    return state


def _create_registry() -> FeatureFlagRegistry | None:
    # No config file is needed in development mode, every flag is enabled
    if settings.Settings.DEVELOPMENT_MODE:
        return None
    return FeatureFlagRegistry(Path(settings.Settings.FEATURE_FLAG_CONFIG))


_registry = _create_registry()


@dataclass(frozen=True)
class FeatureFlag:
    """A flag that exists in this project. Declaring one registers it."""

    name: str
    description: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise exceptions.FeatureFlagDefinitionError(self.name, "name is empty")
        if not self.description.strip():
            raise exceptions.FeatureFlagDefinitionError(
                self.name, "description is empty"
            )
        if _registry is None:
            LOGGER.warning("No feature flag registry, development mode is active.")
            return
        existing = _registry.flag(self.name)
        if existing is None:
            _registry.add(self)
        elif existing != self:
            raise exceptions.FeatureFlagDefinitionError(self.name, "declared twice")

    @property
    def enabled(self) -> bool:
        """Current state, from the config file."""
        if _registry is None:
            return True
        return _registry.flag_state(self.name)

    def __bool__(self) -> bool:
        # Lets you write `if FLAG_SOMETHING:`
        return self.enabled

    def __str__(self) -> str:
        return f"{self.name} - enabled: {self.enabled}"
