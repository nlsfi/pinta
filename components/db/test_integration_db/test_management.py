# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pathlib import Path

import pytest
import sqlmodel

from pinta_db.primary_db.models.management import (
    PointCloudTile,
    ProcessingStatus,
    ProductionArea,
)


@pytest.fixture
def point_cloud_file(tmp_path: Path) -> Path:
    point_cloud_file = tmp_path / "point_cloud_file.bin"
    point_cloud_file.touch()
    return point_cloud_file


def test_production_area_model(db: sqlmodel.Session, point_cloud_file: Path):
    production_area = ProductionArea(
        name="area 1",
        geom="MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))",
    )
    db.add(production_area)

    point_cloud_tile = PointCloudTile(
        geom="Polygon((0 0, 10 0, 10 10, 0 10, 0 0))",
        production_area=production_area,
        file_path=str(point_cloud_file),
    )

    db.add(point_cloud_tile)
    db.commit()

    assert point_cloud_tile.file_path_ == point_cloud_file
    assert production_area.geom_wkt == "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)))"
    assert point_cloud_tile.geom_wkt == "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
    assert production_area.tiles == [point_cloud_tile]


def test_processing_status_last_updated_trigger(db: sqlmodel.Session):
    production_area = ProductionArea(
        name="area 1",
        geom="MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))",
    )
    db.add(production_area)
    db.commit()

    # Inserting a row does not fire the AFTER UPDATE trigger.
    assert production_area.processing_status == ProcessingStatus.NOT_STARTED
    assert production_area.processing_status_last_updated is None

    # Changing the status stamps the timestamp.
    production_area.processing_status = ProcessingStatus.COMPLETED
    db.commit()
    stamped_at = production_area.processing_status_last_updated
    assert stamped_at is not None

    # Updating another column leaves the status unchanged and the timestamp intact.
    production_area.database_name = "db name 1"
    db.commit()
    assert production_area.processing_status_last_updated == stamped_at


def test_production_area_model_update(db: sqlmodel.Session, point_cloud_file: Path):
    production_area = ProductionArea(
        name="area 1",
        geom="MultiPolygon(((0 0, 10 0, 10 10, 0 10, 0 0)))",
    )
    db.add(production_area)

    point_cloud_tile = PointCloudTile(
        geom="Polygon((0 0, 10 0, 10 10, 0 10, 0 0))",
        production_area=production_area,
        file_path=str(point_cloud_file),
    )

    db.add(point_cloud_tile)
    db.commit()

    assert point_cloud_tile.file_path_ == point_cloud_file
    assert production_area.geom_wkt == "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)))"
    assert point_cloud_tile.geom_wkt == "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
    assert production_area.tiles == [point_cloud_tile]

    # get area from db and update tile
    production_area_in_db = db.exec(
        sqlmodel.select(ProductionArea).where(ProductionArea.name == "area 1")
    ).first()
    assert production_area_in_db

    point_cloud_tile2 = PointCloudTile(
        geom="Polygon((0 0, 20 0, 20 20, 0 20, 0 0))",
        production_area=production_area_in_db,
        file_path=str(point_cloud_file),
    )
    db.add(point_cloud_tile2)

    point_cloud_tile3 = PointCloudTile(
        geom="Polygon((0 0, 30 0, 30 30, 0 30, 0 0))",
        production_area=production_area_in_db,
        file_path=str(point_cloud_file),
    )
    db.add(point_cloud_tile3)

    # Update production area geom and tiles
    production_area_in_db.geom = "MultiPolygon(((0 0, 30 0, 30 30, 0 30, 0 0)))"
    production_area_in_db.database_name = "db name 1"
    production_area_in_db.tiles = [point_cloud_tile2, point_cloud_tile3]
    db.commit()

    all_areas = db.exec(sqlmodel.select(ProductionArea)).all()
    assert len(all_areas) == 1
    assert all_areas[0].geom_wkt == "MULTIPOLYGON (((0 0, 30 0, 30 30, 0 30, 0 0)))"
    assert all_areas[0].database_name == "db name 1"
    all_tiles = db.exec(sqlmodel.select(PointCloudTile)).all()
    assert len(all_tiles) == 2
    assert all_tiles[0].geom_wkt == "POLYGON ((0 0, 20 0, 20 20, 0 20, 0 0))"
    assert all_tiles[1].geom_wkt == "POLYGON ((0 0, 30 0, 30 30, 0 30, 0 0))"
