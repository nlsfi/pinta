# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import copy

import affine
import numpy as np
import pytest
import pytest_mock

from pinta_processing import core
from pinta_processing_test_utils import constants


class DummyStage(core.Stage):
    """Dummy stage for testing."""

    def __init__(self, dummy_data: core.RasterDataset | None = None) -> None:
        super().__init__()
        self.dummy_data = dummy_data

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset | None:
        return self.dummy_data if self.dummy_data is not None else data


class ErrorStage(core.Stage):
    """Stage that raises an error."""

    def process(self, _: core.RasterDataset | None) -> core.RasterDataset | None:
        raise RuntimeError


class NullStage(core.Stage):
    """Stage that returns None."""

    def process(self, _: core.RasterDataset | None) -> core.RasterDataset | None:
        return None


class TrackingStage(core.Stage):
    """Stage that tracks received data."""

    def __init__(self) -> None:
        self.received_data = None

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset | None:
        self.received_data = copy.deepcopy(data)
        array = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=constants.DEFAULT_DTYPE)
        return core.RasterDataset(
            array=array,
            transform=constants.DEFAULT_TRANSFORM,
            crs=constants.DEFAULT_CRS,
            nodata=constants.DEFAULT_NODATA,
        )


def test_pipeline_stops_on_error(mocker: pytest_mock.MockerFixture):
    pipeline = DummyStage() | ErrorStage() | DummyStage()

    spy_stage1 = mocker.spy(pipeline.stages[0], "process")
    spy_stage2 = mocker.spy(pipeline.stages[1], "process")
    spy_stage3 = mocker.spy(pipeline.stages[2], "process")

    with pytest.raises(RuntimeError):
        pipeline.execute()

    assert spy_stage1.called
    assert spy_stage2.called
    assert not spy_stage3.called


def test_raster_dataset_converts_array_to_float32():
    dataset = core.RasterDataset(
        array=np.array([[1, 2], [3, 4]], dtype=np.int16),
        transform=constants.DEFAULT_TRANSFORM,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )

    assert dataset.array.dtype == np.float32


def test_raster_dataset_bounds():
    # 3 rows x 4 cols, 1 m pixels, origin at (10, 20) top-left.
    dataset = core.RasterDataset(
        array=np.zeros((3, 4), dtype=np.float32),
        transform=affine.Affine(1.0, 0.0, 10.0, 0.0, -1.0, 20.0),
        crs=constants.DEFAULT_CRS,
        nodata=None,
    )

    # bounds are ordered left, bottom, right, top
    assert dataset.bounds == (10.0, 17.0, 14.0, 20.0)


def test_raster_dataset_empty_is_filled_with_nodata():
    dataset = core.RasterDataset.empty(
        bounds=(10.0, 16.0, 14.0, 20.0),
        pixel_size=2.0,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )

    assert dataset.array.shape == (2, 2)
    assert np.all(dataset.array == constants.DEFAULT_NODATA)
    assert dataset.crs == constants.DEFAULT_CRS
    assert dataset.nodata == constants.DEFAULT_NODATA


def test_raster_dataset_empty_snaps_bounds_outward_to_pixel_lattice():
    # Bounds offset from the 2 m lattice must snap outward to it.
    dataset = core.RasterDataset.empty(
        bounds=(10.5, 16.5, 13.5, 19.5),
        pixel_size=2.0,
        crs=constants.DEFAULT_CRS,
        nodata=constants.DEFAULT_NODATA,
    )

    assert dataset.bounds == (10.0, 16.0, 14.0, 20.0)
    assert dataset.transform.a == 2.0
    assert dataset.transform.e == -2.0


def test_pipeline_executes_all_stages(mocker: pytest_mock.MockerFixture):
    pipeline = DummyStage() | DummyStage() | DummyStage()

    spy_stage1 = mocker.spy(pipeline.stages[0], "process")
    spy_stage2 = mocker.spy(pipeline.stages[1], "process")
    spy_stage3 = mocker.spy(pipeline.stages[2], "process")

    pipeline.execute()

    assert spy_stage1.called
    assert spy_stage2.called
    assert spy_stage3.called


def test_tee_returns_input_unchanged(dataset: core.RasterDataset):
    # Test that Tee returns the input data unchanged
    pipeline = DummyStage() | core.Tee(DummyStage() | DummyStage()) | DummyStage()
    result = pipeline.process(dataset)

    assert result is dataset


def test_tee_sends_independent_copies(dataset: core.RasterDataset):
    # Test that each branch receives an independent copy of the data
    branch1 = TrackingStage()
    branch2 = TrackingStage()
    pipeline = DummyStage() | core.Tee(branch1 | DummyStage()) | branch2
    original_array = dataset.array.copy()
    pipeline.process(dataset)

    # Original dataset should be unchanged
    assert np.array_equal(dataset.array, original_array)

    # Each branch received independent copies
    assert branch1.received_data is not None
    assert branch1.received_data is not dataset
    assert branch2.received_data is not None
    assert branch2.received_data is not dataset
    assert branch1.received_data is not branch2.received_data
    # Arrays have identical content but are different objects
    assert np.array_equal(branch1.received_data.array, branch2.received_data.array)


def test_zip(dataset: core.RasterDataset):
    original_array = dataset.array.copy()
    pipeline = DummyStage() | core.Zip(DummyStage(dummy_data=dataset))
    result = pipeline.process(dataset)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(item is dataset for item in result)
    # Datasets should not be modified
    assert all(np.array_equal(item.array, original_array) for item in result)


def test_zip_with_pipeline(dataset: core.RasterDataset):
    pipeline = DummyStage() | core.Zip(DummyStage() | DummyStage(dummy_data=dataset))
    result = pipeline.process(dataset)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(item is dataset for item in result)


def test_zip_multiple_inputs(dataset: core.RasterDataset):
    other1 = DummyStage(dummy_data=dataset)
    other2 = DummyStage(dummy_data=dataset)
    other3 = DummyStage(dummy_data=dataset)
    pipeline = DummyStage() | core.Zip(other1, other2, other3)
    result = pipeline.process(dataset)

    assert isinstance(result, tuple)
    assert len(result) == 4
    assert all(item is dataset for item in result)


def test_zip_without_input_as_first_stage(dataset: core.RasterDataset):
    # Test that Zip works as the first stage without input
    pipeline = core.Zip(DummyStage(dummy_data=dataset))
    result = pipeline.execute()

    assert isinstance(result, tuple)
    assert len(result) == 1
    assert result[0] is dataset


def test_zip_with_branch_returning_none(dataset: core.RasterDataset):
    # Test that Zip works when a branch returns None
    pipeline = DummyStage() | core.Zip(NullStage())
    result = pipeline.process(dataset)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] is dataset
    assert result[1] is None


def test_zip_only_stage_with_no_others():
    pipeline = core.Zip()
    result = pipeline.execute()

    assert result == ()
