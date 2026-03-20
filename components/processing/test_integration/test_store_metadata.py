# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
import sqlmodel
from geoalchemy2.shape import to_shape
from pinta_db.models.management import PointCloudTile, ProductionArea
from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils
from pinta_test_utils.pinta_utils import get_test_data_path

from pinta_processing.scripts.process_metadata import (
    add_tiles_to_production_area,
    create_point_cloud_tiles_from_folder,
    find_production_area,
)

if TYPE_CHECKING:
    from sqlmodel import Session


@pytest.fixture
def session(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_db(worker_id)
    with engine_utils.get_session(db_utils.get_writer_credentials(db_name)) as session:
        yield session
        session.close()


def test_create_and_update_production_area(
    pytestconfig: pytest.Config, session: "Session"
):
    folder_path = get_test_data_path(pytestconfig, "2025/production_area_1")

    # store 5 tiles
    tiles = create_point_cloud_tiles_from_folder(folder_path)
    production_area_5 = find_production_area(folder_path, session)
    add_tiles_to_production_area(production_area_5, tiles[:5], session)
    session.commit()

    all_areas = session.exec(sqlmodel.select(ProductionArea)).all()
    assert len(all_areas) == 1
    assert all_areas[0].name == "production_area_1"
    area_polygon = to_shape(all_areas[0].geom)
    assert pytest.approx(area_polygon.area, rel=1e-3) == 5000000

    all_tiles = session.exec(sqlmodel.select(PointCloudTile)).all()
    assert len(all_tiles) == 5

    # update and store all 18 tiles
    tiles = create_point_cloud_tiles_from_folder(folder_path)
    production_area_all = find_production_area(folder_path, session)
    add_tiles_to_production_area(production_area_all, tiles, session)
    session.commit()

    all_areas = session.exec(sqlmodel.select(ProductionArea)).all()
    assert len(all_areas) == 1
    assert all_areas[0].name == "production_area_1"
    area_polygon = to_shape(all_areas[0].geom)
    assert pytest.approx(area_polygon.area, rel=1e-4) == 18000000

    all_tiles = session.exec(sqlmodel.select(PointCloudTile)).all()
    assert len(all_tiles) == 18
