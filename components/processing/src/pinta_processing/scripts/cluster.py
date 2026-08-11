# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import logging
import pathlib

import sqlalchemy
from pinta_common import Settings
from sqlmodel import Session

LOGGER = logging.getLogger(__name__)

CLUSTER_SQL_PATH = pathlib.Path(__file__).parent / "cluster_all.sql"


def cluster_diff_polygons(session: Session) -> None:
    """Cluster difference polygons into reference.update_area_suggestion.

    Runs the clustering SQL, appending to any existing suggestions. The table is
    append only: other producers, such as the masked update area suggestions,
    write into it in parallel, so clustering must not clear their rows. The
    cluster energy density is scaled by the DEM pixel area (pixel size squared)
    so that the per-polygon energy sums are weighted by the area a raster pixel
    covers.
    """
    pixel_area = Settings.DB_DEM_PIXEL_SIZE**2
    LOGGER.debug("Clustering difference polygons with pixel area %s", pixel_area)

    sql = CLUSTER_SQL_PATH.read_text()
    session.exec(  # type: ignore[call-overload]
        sqlalchemy.text(sql).bindparams(pixel_area=pixel_area)
    )
    session.commit()
