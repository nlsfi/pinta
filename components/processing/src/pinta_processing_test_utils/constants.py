# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import affine
import numpy as np

DEFAULT_CRS = "EPSG:3067"
DEFAULT_TRANSFORM = affine.Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)
DEFAULT_DTYPE = np.float32
DEFAULT_NODATA = -9999.0
