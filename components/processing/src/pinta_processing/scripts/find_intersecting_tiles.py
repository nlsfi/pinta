# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import pathlib

import sqlalchemy
import sqlmodel
from geoalchemy2 import WKTElement
from pinta_common import Settings
from pinta_db.primary_db.models.management import PointCloudTile
from sqlmodel import Session

from pinta_processing.utils import tm35_map_sheet_utils


def find_neighboring_tm35_laz_files(
    laz_file_path: pathlib.Path,
    buffer_meters: float,
    session: Session,
) -> list[pathlib.Path]:
    """Find paths of LAZ files intersecting the buffered TM35 tile bounding box."""
    geometry = tm35_map_sheet_utils.calculate_buffered_sheet_geometry(
        laz_file_path.stem, buffer_meters
    )
    search_area = WKTElement(geometry.wkt, srid=int(Settings.DB_SRID))

    statement = sqlmodel.select(PointCloudTile).where(
        sqlalchemy.func.ST_Intersects(PointCloudTile.geom, search_area)
    )
    return [
        tile.file_path_
        for tile in session.exec(statement).all()
        if tile.file_path_.stem != laz_file_path.stem
    ]
