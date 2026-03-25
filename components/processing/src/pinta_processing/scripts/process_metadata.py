# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


from pathlib import Path

import laspy
import shapely
import sqlmodel
from pinta_db.models.management import PointCloudTile, ProductionArea
from shapely import ops
from shapely.geometry import MultiPolygon
from sqlmodel import Session

POINT_CLOUD_BBOX_BUFFER_M = 0.1


def process_metadata_in_folder(folder_path: Path, session: Session) -> None:
    """Process all LAS/LAZ files in folder.

    Create PointCloudTile objects and calculate a bounding box for a ProductionArea.
    If a production area already exists, the old tiles are overridden in the database
    and the production area is updated.
    """
    tiles = create_point_cloud_tiles_from_folder(folder_path)
    production_area = find_production_area(folder_path, session)
    add_tiles_to_production_area(production_area, tiles, session)
    session.commit()


def create_point_cloud_tile(file_path: Path) -> PointCloudTile:
    """Create PointCloudTile with 2D bounding box from LAS/LAZ header."""
    with laspy.open(file_path) as las:
        mins = las.header.mins
        maxs = las.header.maxs

        bbox = shapely.box(mins[0], mins[1], maxs[0], maxs[1])
        return PointCloudTile(file_path=str(file_path), geom=bbox.wkt)


def create_point_cloud_tiles_from_folder(folder_path: Path) -> list[PointCloudTile]:
    """Create PointCloudTile from each point cloud file in folder."""
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(folder)

    tiles = []

    for file_path in folder.glob("*"):
        # Skip non-LAS/LAZ files or "copc.laz" files
        if (
            file_path.suffix.lower() in [".las", ".laz"]
            and "copc.laz" not in file_path.name.lower()
        ):
            tile = create_point_cloud_tile(file_path)
            tiles.append(tile)

    if not tiles:
        msg = f"No LAS/LAZ files found in folder: {folder}"
        raise ValueError(msg)

    return tiles


def add_tiles_to_production_area(
    production_area: ProductionArea, tiles: list[PointCloudTile], session: Session
) -> None:
    """Link production area to tiles and calculate bounding box."""
    polygons = []

    for tile in tiles:
        polygon = shapely.wkt.loads(tile.geom)
        polygons.append(polygon.buffer(POINT_CLOUD_BBOX_BUFFER_M))
        tile.production_area = production_area
        session.add(tile)

    production_area.tiles = tiles

    geom = ops.unary_union(polygons)
    if geom.geom_type == "Polygon":
        geom = MultiPolygon([geom])
    production_area.geom = geom.wkt


def find_production_area(folder_path: Path, session: Session) -> ProductionArea:
    """Find a ProductionArea from the database or create a new one."""
    statement = sqlmodel.select(ProductionArea).where(
        ProductionArea.name == folder_path.name
    )
    area_in_db = session.exec(statement).first()
    if area_in_db:
        return area_in_db
    production_area = ProductionArea(name=folder_path.name)
    session.add(production_area)
    return production_area
