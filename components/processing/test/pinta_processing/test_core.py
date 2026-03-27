# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import copy

import numpy as np
import pytest
import pytest_mock

from pinta_processing import core


class DummyStage(core.Stage):
    """Dummy stage for testing."""

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset | None:
        return data


class ErrorStage(core.Stage):
    """Stage that raises an error."""

    def process(self, _: core.RasterDataset | None) -> core.RasterDataset | None:
        raise RuntimeError


class TrackingStage(core.Stage):
    """Stage that tracks received data."""

    def __init__(self) -> None:
        self.received_data = None

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset | None:
        self.received_data = copy.deepcopy(data)
        if data is not None:
            data.array[0, 0] = 999.0
        return data


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
    pipeline = DummyStage() | core.Tee(branch1, branch2) | DummyStage()
    original_array = dataset.array.copy()
    pipeline.process(dataset)

    # Original dataset should be unchanged
    assert np.array_equal(dataset.array, original_array)

    # Each branch received independent copies
    assert branch1.received_data is not None
    assert branch2.received_data is not None
    assert branch1.received_data is not branch2.received_data
    # Arrays have identical content but are different objects
    assert np.array_equal(branch1.received_data.array, branch2.received_data.array)
