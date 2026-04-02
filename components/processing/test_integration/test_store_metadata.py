# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

import geoalchemy2.shape
import pytest
import sqlmodel
from pinta_db.models.management import PointCloudTile, ProductionArea
from pinta_test_utils import pinta_utils

from pinta_processing.scripts import process_metadata

if typing.TYPE_CHECKING:
    from sqlmodel import Session


def test_create_and_update_production_area(session: "Session"):
    folder_path = pinta_utils.get_test_data_path("point_clouds/2025/production_area_1")

    # store 5 tiles
    tiles = process_metadata.create_point_cloud_tiles_from_folder(folder_path)
    production_area_5 = process_metadata.find_production_area(folder_path, session)
    process_metadata.add_tiles_to_production_area(production_area_5, tiles[:5], session)
    session.commit()

    all_areas = session.exec(sqlmodel.select(ProductionArea)).all()
    assert len(all_areas) == 1
    assert all_areas[0].name == "production_area_1"
    area_polygon = geoalchemy2.shape.to_shape(all_areas[0].geom)
    assert pytest.approx(area_polygon.area, rel=1e-3) == 5000000

    all_tiles = session.exec(sqlmodel.select(PointCloudTile)).all()
    assert len(all_tiles) == 5

    # update and store all 18 tiles
    tiles = process_metadata.create_point_cloud_tiles_from_folder(folder_path)
    production_area_all = process_metadata.find_production_area(folder_path, session)
    process_metadata.add_tiles_to_production_area(production_area_all, tiles, session)
    session.commit()

    all_areas = session.exec(sqlmodel.select(ProductionArea)).all()
    assert len(all_areas) == 1
    assert all_areas[0].name == "production_area_1"
    area_polygon = geoalchemy2.shape.to_shape(all_areas[0].geom)
    assert pytest.approx(area_polygon.area, rel=1e-4) == 18000000

    all_tiles = session.exec(sqlmodel.select(PointCloudTile)).all()
    assert len(all_tiles) == 18
