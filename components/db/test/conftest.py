# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
from pinta_test_utils.xdist_utils import get_number_of_workers


@pytest.hookimpl
def pytest_xdist_auto_num_workers(config: "pytest.Config"):
    return get_number_of_workers(config)
