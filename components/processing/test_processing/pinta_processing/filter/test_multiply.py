# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import numpy as np
import pytest

from pinta_processing import core, exceptions
from pinta_processing.filters import MultiplyValues


def test_multiply_values(dataset: core.RasterDataset):
    """Test multiplication: data transform, nodata preservation, and metadata."""
    factor = 2.0
    stage = MultiplyValues(factor=factor)
    result = stage.process(dataset)

    # Basic multiplication: [1, -9999, 3, 4] * 2 = [2, -9999, 6, 8]
    # Nodata value (-9999) should remain unchanged
    expected = np.array([[2.0, -9999.0], [6.0, 8.0]])
    assert np.allclose(result.array, expected)

    # Verify nodata is preserved
    assert result.nodata == -9999.0

    # Verify metadata is preserved
    assert result.transform == dataset.transform
    assert result.crs == dataset.crs


def test_multiply_values_with_zero_factor(dataset: core.RasterDataset):
    """Test multiplication with zero factor."""
    stage = MultiplyValues(factor=0.0)
    result = stage.process(dataset)

    # All valid values become 0, nodata stays -9999
    expected = np.array([[0.0, -9999.0], [0.0, 0.0]])
    assert np.allclose(result.array, expected)


def test_multiply_values_with_negative_factor(dataset: core.RasterDataset):
    """Test multiplication with negative factor."""
    stage = MultiplyValues(factor=-1.5)
    result = stage.process(dataset)

    expected = np.array([[-1.5, -9999.0], [-4.5, -6.0]])
    assert np.allclose(result.array, expected)


def test_multiply_values_invalid_input():
    """Test that invalid input raises InvalidStageInputError."""
    stage = MultiplyValues(factor=2.0)

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process("not a dataset")

    with pytest.raises(exceptions.InvalidStageInputError):
        stage.process(None)


def test_multiply_values_does_not_modify_input(dataset: core.RasterDataset):
    """Test that the input array is not modified."""
    original = dataset.array.copy()

    stage = MultiplyValues(factor=2.0)
    stage.process(dataset)

    # Original array should not be modified
    assert np.allclose(dataset.array, original)
