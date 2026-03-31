# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path


def get_test_data_path(relative_path: str | Path, check_if_exists: bool = True) -> Path:
    """
    Return the absolute path to a file or folder inside test_data, relative to the project root.
    """
    project_root = Path(__file__).parent.parent.parent.parent.parent
    test_data_dir = project_root / "test_data"
    if check_if_exists:
        assert test_data_dir.exists(), (
            f"test_data directory not found at {test_data_dir}"
        )
    resource = test_data_dir / Path(relative_path)
    if check_if_exists:
        assert resource.exists(), f"Resource not found at {resource}"
    return resource
