# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pinta_test_utils import pinta_utils

from pinta_processing import core, filters, pipelines, reader, writer


def rasterio_to_geotiff_with_tee_pipeline(
    input_path: str, output_path: str, tee_output_path: str
) -> core.Pipeline:
    """Read rasterio input and write it as geotiff."""
    return (
        reader.RasterioReader(input_path)
        | core.Tee(filters.MultiplyValues(2.0) | writer.GeotiffWriter(tee_output_path))
        | writer.GeotiffWriter(output_path)
    )


def _verify_pipeline_output(input_path: str, output_path: Path) -> None:
    assert output_path.exists(), "Output file was not created"

    with rasterio.open(input_path) as src_in:
        input_array = src_in.read(1)
        input_crs = src_in.crs
        input_transform = src_in.transform
        input_nodata = src_in.nodata

    with rasterio.open(str(output_path)) as src_out:
        output_array = src_out.read(1)
        output_crs = src_out.crs
        output_transform = src_out.transform
        output_nodata = src_out.nodata

    # Verify array data is identical
    assert np.array_equal(input_array, output_array), "Array data does not match"

    # Verify metadata is preserved
    assert output_crs == input_crs, "CRS not preserved"
    assert output_transform == input_transform, "Transform not preserved"
    assert output_nodata == input_nodata, "Nodata not preserved"


def test_rasterio_to_geotiff_pipeline_with_geotiff_input(
    pytestconfig: pytest.Config,
):
    file_path = pinta_utils.get_test_data_path(pytestconfig, "processing/dem.tif")
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "output.tif"
        pipeline = pipelines.rasterio_to_geotiff_pipeline(
            str(file_path), str(output_path)
        )
        pipeline.execute()
        _verify_pipeline_output(str(file_path), output_path)


def test_rasterio_to_geotiff_pipeline_with_asc_input(pytestconfig: pytest.Config):
    zip_path = pinta_utils.get_test_data_path(pytestconfig, "processing/dem.asc.zip")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_path = tmp_path / "output.tif"
        unzipped_path = tmp_path / "dem.asc"

        # Unzip the ASCII grid file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_path)

        pipeline = pipelines.rasterio_to_geotiff_pipeline(
            str(unzipped_path), str(output_path)
        )
        pipeline.execute()

        _verify_pipeline_output(str(unzipped_path), output_path)


def test_rasterio_to_geotiff_pipeline_with_tee(pytestconfig: pytest.Config):
    file_path = pinta_utils.get_test_data_path(pytestconfig, "processing/dem.tif")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        main_output_path = tmp_path / "main_output.tif"
        tee_output_path = tmp_path / "tee_output.tif"
        pipeline = rasterio_to_geotiff_with_tee_pipeline(
            str(file_path), str(main_output_path), str(tee_output_path)
        )
        pipeline.execute()

        # Verify both outputs are valid GeoTIFF files
        assert main_output_path.exists()
        with rasterio.open(str(main_output_path)):
            pass

        assert tee_output_path.exists()
        with rasterio.open(str(tee_output_path)):
            pass
