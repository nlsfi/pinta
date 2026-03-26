# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import shapely.wkt
from pinta_db.models.management import PointCloudTile, ProductionArea
from pinta_test_utils import pinta_utils
from sqlmodel import Session

from pinta_processing.scripts import process_metadata


def test_create_point_cloud_tile(pytestconfig: pytest.Config):
    file_path = pinta_utils.get_test_data_path(
        pytestconfig, "point_clouds/2025/production_area_1/T5124H1_1.laz"
    )

    tile = process_metadata.create_point_cloud_tile(file_path)

    assert tile.file_path == str(file_path)
    assert (
        tile.geom
        == "POLYGON ((543000 7380000.02, 543000 7381000, 542000.01 7381000, 542000.01 7380000.02, 543000 7380000.02))"
    )


def test_create_point_cloud_tiles_from_folder(pytestconfig: pytest.Config):
    folder_path = pinta_utils.get_test_data_path(
        pytestconfig, "point_clouds/2025/production_area_1"
    )
    tiles = process_metadata.create_point_cloud_tiles_from_folder(folder_path)

    assert len(tiles) == 18
    assert all(t.geom is not None for t in tiles)
    tiles.sort(key=lambda tile: tile.file_path)
    assert tiles[0].file_path == str(folder_path) + "/T5124H1_1.laz"
    assert tiles[1].file_path == str(folder_path) + "/T5124H1_2.laz"
    assert tiles[2].file_path == str(folder_path) + "/T5124H1_3.laz"
    assert tiles[3].file_path == str(folder_path) + "/T5124H1_4.laz"
    assert tiles[4].file_path == str(folder_path) + "/T5124H1_5.laz"
    assert tiles[5].file_path == str(folder_path) + "/T5124H1_6.laz"
    assert tiles[6].file_path == str(folder_path) + "/T5124H1_7.laz"
    assert tiles[7].file_path == str(folder_path) + "/T5124H1_8.laz"
    assert tiles[8].file_path == str(folder_path) + "/T5124H1_9.laz"
    assert tiles[9].file_path == str(folder_path) + "/T5124H3_1.laz"
    assert tiles[10].file_path == str(folder_path) + "/T5124H3_2.laz"
    assert tiles[11].file_path == str(folder_path) + "/T5124H3_3.laz"
    assert tiles[12].file_path == str(folder_path) + "/T5124H3_4.laz"
    assert tiles[13].file_path == str(folder_path) + "/T5124H3_5.laz"
    assert tiles[14].file_path == str(folder_path) + "/T5124H3_6.laz"
    assert tiles[15].file_path == str(folder_path) + "/T5124H3_7.laz"
    assert tiles[16].file_path == str(folder_path) + "/T5124H3_8.laz"
    assert tiles[17].file_path == str(folder_path) + "/T5124H3_9.laz"


def test_create_point_cloud_tiles_from_folder_when_folder_not_found():
    invalid_path = "/this/folder/does/not/exist"

    with pytest.raises(FileNotFoundError, match=invalid_path):
        process_metadata.create_point_cloud_tiles_from_folder(invalid_path)


def test_create_point_cloud_tiles_from_folder_when_no_laz_files_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        with pytest.raises(
            ValueError, match=f"No LAS/LAZ files found in folder: {tmpdir_path}"
        ):
            process_metadata.create_point_cloud_tiles_from_folder(tmpdir_path)


def test_add_tiles_to_production_area():
    mock_session = MagicMock(spec=Session)
    production_area = ProductionArea(name="area 1")
    tile_1 = PointCloudTile(geom="Polygon((0 0, 100 0, 100 100, 0 100, 0 0))")
    tile_2 = PointCloudTile(geom="Polygon((0 100, 100 100, 100 200, 0 200, 0 100))")

    process_metadata.add_tiles_to_production_area(
        production_area, [tile_1, tile_2], mock_session
    )

    assert production_area.tiles == [tile_1, tile_2]
    assert tile_1.production_area == production_area
    assert tile_2.production_area == production_area
    area_polygon = shapely.wkt.loads(production_area.geom)
    assert pytest.approx(area_polygon.area, rel=1e-5) == 20060  # 100 x 100 x 2 + buffer
