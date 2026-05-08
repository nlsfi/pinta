# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


class MissingEnvironmentError(RuntimeError):
    def __init__(self, env_variable_name: str) -> None:
        super().__init__(
            f"Environment configuration error: {env_variable_name}",
        )
