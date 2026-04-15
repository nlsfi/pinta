# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pinta_dags.sensors.folder_hash_sensor import FolderHashSensor

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_folder_hash_sensor_raises_skip_when_no_changes(
    mocker: "MockerFixture",
) -> None:
    sensor = FolderHashSensor(task_id="check_for_changes", base_path="/some/path")
    mocker.patch.object(sensor, "_find_changed_folders", return_value=[])

    from airflow.exceptions import AirflowSkipException

    with pytest.raises(AirflowSkipException):
        sensor.execute({})  # type: ignore[arg-type]


def test_folder_hash_sensor_returns_changed_folders(
    mocker: "MockerFixture",
) -> None:
    sensor = FolderHashSensor(task_id="check_for_changes", base_path="/some/path")
    expected = [{"folder_path": "/some/path/2025/prod1", "new_hash": "abc123"}]
    mocker.patch.object(sensor, "_find_changed_folders", return_value=expected)

    result = sensor.execute({})  # type: ignore[arg-type]

    assert result == expected


def test_folder_hash_sensor_find_changed_folders(
    tmp_path: Path,
    mocker: "MockerFixture",
) -> None:
    area_dir = tmp_path / "2025" / "production_area_1"
    area_dir.mkdir(parents=True)
    (area_dir / "tile.laz").write_bytes(b"fake laz data")

    sensor = FolderHashSensor(task_id="check_for_changes", base_path=str(tmp_path))
    mocker.patch(
        "pinta_dags.sensors.folder_hash_sensor.Variable.get",
        return_value=None,
    )

    result = sensor._find_changed_folders()

    assert len(result) == 1
    assert result[0]["folder_path"] == str(area_dir.relative_to(tmp_path))
    assert len(result[0]["new_hash"]) == 64  # SHA-256 hex digest length


def test_folder_hash_sensor_no_change_when_hash_matches(
    tmp_path: Path,
    mocker: "MockerFixture",
) -> None:
    area_dir = tmp_path / "2025" / "production_area_1"
    area_dir.mkdir(parents=True)
    (area_dir / "tile.laz").write_bytes(b"fake laz data")

    sensor = FolderHashSensor(task_id="check_for_changes", base_path=str(tmp_path))
    existing_hash = sensor._hash_folder(area_dir)
    mocker.patch(
        "pinta_dags.sensors.folder_hash_sensor.Variable.get",
        return_value=existing_hash,
    )

    result = sensor._find_changed_folders()

    assert result == []
