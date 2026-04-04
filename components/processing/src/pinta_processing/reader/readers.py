# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import pathlib
import tempfile
import zipfile

import rasterio

from pinta_processing import core


class RasterioReader(core.Stage):
    """Read raster files using rasterio.

    Reads the first band and extracts georeferencing information
    (transform, CRS, nodata values) from the file metadata.
    """

    def __init__(self, path: str | pathlib.Path) -> None:
        """Initialize RasterioReader."""
        self.path = pathlib.Path(path)

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:  # noqa: ARG002
        """Read raster file and return RasterDataset."""
        if self.path.suffix.lower() == ".zip":
            self.path = self._extract_from_zip(self.path)

        return self._rasterio_to_dataset()

    def _extract_from_zip(self, zip_path: pathlib.Path) -> pathlib.Path:
        """Extract raster file from zip archive and return path.

        Raises ValueError if zip contains 0 or multiple files.
        """
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            file_list = zip_file.namelist()
            # Filter out directories
            file_list = [f for f in file_list if not f.endswith("/")]

            if len(file_list) == 0:
                msg = "No files found in zip archive"
                raise ValueError(msg)
            if len(file_list) > 1:
                msg = f"Zip archive contains {len(file_list)} files, expected exactly 1"
                raise ValueError(msg)

            # Create temporary directory and extract
            self._temp_dir = tempfile.TemporaryDirectory()
            zip_file.extractall(self._temp_dir.name)

        return pathlib.Path(self._temp_dir.name) / file_list[0]

    def _rasterio_to_dataset(self) -> core.RasterDataset:
        """Convert rasterio dataset to RasterDataset."""
        with rasterio.open(self.path) as src:
            return core.RasterDataset.from_rasterio(src)
