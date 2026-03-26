# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_processing import core, reader, writer


def rasterio_to_geotiff_pipeline(input_path: str, output_path: str) -> core.Pipeline:
    """Read rasterio input and write it as geotiff."""
    return reader.RasterioReader(input_path) | writer.GeotiffWriter(output_path)
