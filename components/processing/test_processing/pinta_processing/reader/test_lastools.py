# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pathlib
import subprocess
import typing
from collections.abc import Callable
from typing import Any

import pytest

from pinta_processing import core
from pinta_processing.exceptions import LasToolsError
from pinta_processing.reader import lastools

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


class DummyLASToolsReader(lastools.LASToolsReader):
    executable = "dummy_tool"

    def _get_tool_specific_params(self) -> list[str]:
        return []


def _make_run_side_effect(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    create_output: bool = True,
) -> Callable[..., subprocess.CompletedProcess]:
    """Build a side_effect for subprocess.run that also creates the output file."""

    def side_effect(command: list[str], **_: Any) -> subprocess.CompletedProcess:
        if create_output and returncode == 0:
            out_path = pathlib.Path(command[command.index("-o") + 1])
            out_path.touch()
        return subprocess.CompletedProcess(
            args=command, returncode=returncode, stdout=stdout, stderr=stderr
        )

    return side_effect


def _make_blast2dem_reader(**overrides: Any) -> lastools.Blast2DemReader:
    params: dict[str, Any] = {
        "input_path": pathlib.Path("/data/input.laz"),
        "step": 2,
        "crs": "EPSG:3067",
        "keep_class": [2, 9],
    }
    params.update(overrides)
    return lastools.Blast2DemReader(**params)


@pytest.fixture
def mock_rasterio_reader(
    mocker: "MockerFixture", dataset: core.RasterDataset
) -> "MagicMock":
    mock_class = mocker.patch.object(lastools.readers, "RasterioReader", autospec=True)
    mock_class.return_value.process.return_value = dataset
    return mock_class


def test_blast2dem_reader_builds_command(
    mocker: "MockerFixture", mock_rasterio_reader: "MagicMock"
):
    run_mock = mocker.patch.object(
        lastools.subprocess, "run", side_effect=_make_run_side_effect()
    )

    stage = _make_blast2dem_reader()
    stage.process(None)

    run_mock.assert_called_once()
    command = run_mock.call_args.args[0]
    assert command[0] == "/lastools/bin/las2dem_new64"
    assert command[command.index("-i") + 1] == str(stage.input_path)
    assert command[command.index("-epsg") + 1] == "3067"
    assert command[command.index("-step") + 1] == "2"
    keep_class_idx = command.index("-keep_class")
    assert command[keep_class_idx + 1 : keep_class_idx + 3] == ["2", "9"]


def test_blast2dem_reader_appends_extra_params(
    mocker: "MockerFixture", mock_rasterio_reader: "MagicMock"
):
    run_mock = mocker.patch.object(
        lastools.subprocess, "run", side_effect=_make_run_side_effect()
    )

    stage = _make_blast2dem_reader(
        extra_lastools_params={"thin_with_grid": 0.5, "elevation": "average"},
    )
    stage.process(None)

    command = run_mock.call_args.args[0]
    assert command[command.index("-thin_with_grid") + 1] == "0.5"
    assert command[command.index("-elevation") + 1] == "average"


def test_blast2dem_reader_expands_list_valued_params(
    mocker: "MockerFixture", mock_rasterio_reader: "MagicMock"
):
    run_mock = mocker.patch.object(
        lastools.subprocess, "run", side_effect=_make_run_side_effect()
    )

    stage = _make_blast2dem_reader(
        extra_lastools_params={"neighbors": ["a.laz", "b.laz", "c.laz"]},
    )
    stage.process(None)

    command = run_mock.call_args.args[0]
    neighbors_idx = command.index("-neighbors")
    assert command[neighbors_idx + 1 : neighbors_idx + 4] == ["a.laz", "b.laz", "c.laz"]


def test_lastools_reader_returns_rasterio_dataset(
    mocker: "MockerFixture",
    mock_rasterio_reader: "MagicMock",
    dataset: core.RasterDataset,
):
    mocker.patch.object(lastools.subprocess, "run", side_effect=_make_run_side_effect())

    stage = _make_blast2dem_reader()
    result = stage.process(None)

    assert result is dataset
    # RasterioReader is constructed with the temp output path and configured CRS.
    rasterio_call = mock_rasterio_reader.call_args
    assert rasterio_call.kwargs["crs"] == "EPSG:3067"
    assert rasterio_call.kwargs["path"].name == "output.tif"


def test_lastools_reader_raises_when_command_fails(
    mocker: "MockerFixture", mock_rasterio_reader: "MagicMock"
):
    mocker.patch.object(
        lastools.subprocess,
        "run",
        side_effect=_make_run_side_effect(returncode=1, stderr="boom"),
    )

    stage = _make_blast2dem_reader()
    with pytest.raises(LasToolsError, match="boom"):
        stage.process(None)


def test_lastools_reader_raises_when_output_file_missing(
    mocker: "MockerFixture", mock_rasterio_reader: "MagicMock"
):
    mocker.patch.object(
        lastools.subprocess,
        "run",
        side_effect=_make_run_side_effect(create_output=False),
    )

    stage = _make_blast2dem_reader()
    with pytest.raises(LasToolsError, match="was not created"):
        stage.process(None)


def test_lastools_reader_base_class_requires_tool_specific_params():
    stage = lastools.LASToolsReader(
        input_path=pathlib.Path("/data/input.laz"), crs="EPSG:3067"
    )
    with pytest.raises(NotImplementedError):
        stage._get_tool_specific_params()
