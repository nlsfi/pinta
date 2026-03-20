# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path

import pytest


def get_test_data_path(pytestconfig: pytest.Config, relative_path: str | Path) -> Path:
    """
    Return the absolute path to a file or folder inside test_data, relative to the project root.
    """
    return Path(pytestconfig.rootpath) / "test_data" / Path(relative_path)
