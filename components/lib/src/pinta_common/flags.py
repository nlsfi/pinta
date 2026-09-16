# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_common import constants
from pinta_common.feature_flag_registry import FeatureFlag

FLAG_TEST_DAG_PRINT_CURRENT_TIME = FeatureFlag(
    name="FLAG_TEST_DAG_PRINT_CURRENT_TIME",
    description=f"Prints the current time in the {constants.DAG_ID_HELLO_WORLD} DAG",
)
