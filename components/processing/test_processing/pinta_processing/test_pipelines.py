# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from pinta_processing import pipelines


def test_blast2dem_to_postgis_uses_extra_param_defaults(mocker: MockerFixture) -> None:

    blast2dem_reader = mocker.patch(
        "pinta_processing.reader.Blast2DemReader",
        return_value=MagicMock(),
    )

    pipelines.blast2dem_to_postgis(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        input_path=Path("/tmp/dir/N5122B4_1.laz"),
        step=1,
        keep_class=[2],
    )

    assert blast2dem_reader.call_args.kwargs["extra_lastools_params"] == {
        "buffered": 300,
        "kill": 300,
        "ncols": 500,
        "nrows": 500,
        "ll": [503000, 6903000],
    }


def test_blast2dem_to_postgis_override_extra_param_defaults(
    mocker: MockerFixture,
) -> None:

    blast2dem_reader = mocker.patch(
        "pinta_processing.reader.Blast2DemReader",
        return_value=MagicMock(),
    )

    pipelines.blast2dem_to_postgis(
        primary_session=MagicMock(),
        job_session=MagicMock(),
        input_path=Path("/tmp/dir/N5122B4_1.laz"),
        step=1,
        keep_class=[2],
        extra_lastools_params={
            "buffered": 100,
            "ncols": 200,
            "neighbors": ["a.laz", "b.laz", "c.laz"],
            "ll": [111, 222],
        },
    )

    assert blast2dem_reader.call_args.kwargs["extra_lastools_params"] == {
        "buffered": 100,
        "kill": 300,
        "ncols": 200,
        "nrows": 500,
        "ll": [111, 222],
        "neighbors": ["a.laz", "b.laz", "c.laz"],
    }
