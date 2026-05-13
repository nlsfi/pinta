# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


class InvalidStageInputError(Exception):
    """Raised when a pipeline stage receives an invalid input type."""

    def __init__(self, stage_name: str, expected_type: str, received_type: str) -> None:
        self.stage_name = stage_name
        self.expected_type = expected_type
        self.received_type = received_type
        super().__init__(f"{stage_name} expected {expected_type}, got {received_type}")


class LasToolsError(Exception):
    """Raised when an error occurs in LasTools."""

    def __init__(self, stage_name: str, command: str, error_message: str) -> None:
        super().__init__(
            f"Error with lastools in {stage_name} with {command}: {error_message}"
        )
