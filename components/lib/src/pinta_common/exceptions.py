# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterable
from pathlib import Path


class MissingEnvironmentError(RuntimeError):
    def __init__(self, env_variable_name: str) -> None:
        super().__init__(
            f"Environment configuration error: {env_variable_name}",
        )


class FeatureFlagError(Exception):
    pass


class FeatureFlagConfigError(FeatureFlagError):
    def __init__(self, config_file: Path, reason: str) -> None:
        super().__init__(f"Invalid feature flag config {config_file}: {reason}")


class FeatureFlagDefinitionError(FeatureFlagError):
    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f'Invalid feature flag "{name}": {reason}')


class MissingFeatureFlagError(FeatureFlagError):
    def __init__(self, config_file: Path, names: Iterable[str]) -> None:
        self.names = sorted(names)
        super().__init__(
            f"Feature flags missing from {config_file}: {', '.join(self.names)}"
        )
