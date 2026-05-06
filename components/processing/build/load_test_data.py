# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import argparse
import logging
import pathlib

import sqlalchemy
import sqlmodel
from pinta_db_utils.postgis import raster

from pinta_processing import pipelines

LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-i",
    "--input-dir",
    type=str,
    help="Input folder",
)
parser.add_argument(
    "-c",
    "--db-connection",
    type=str,
    help="Postgres connection string",
)


def run(connection_string: str, test_data_dir: str) -> None:
    """Load rasterio compatible data into db."""
    engine = sqlalchemy.create_engine(connection_string)
    folder = pathlib.Path(test_data_dir)
    with sqlmodel.Session(engine) as session:
        # dem.dem exists, just init staging table
        raster.initialize_raster_table(session, "dem", "dem")
        # overviews exists, just init staging table for each overview
        raster.initialize_overview_tables(session, "dem", "dem")

        for file_path in list(folder.glob("*.asc")):
            LOGGER.info("Processing file %s", file_path)
            pipeline = pipelines.rasterio_to_postgis(
                session=session, input_path=file_path, schema="dem", table_name="dem"
            )
            pipeline.execute()

        raster.merge_staging_tables("dem", "dem", session=session)
        for level in raster.DEFAULT_OVERVIEW_LEVELS:
            overview_table = raster.OVERVIEW_TABLE_NAME.format(
                level=level, table_name="dem"
            )
            raster.merge_staging_tables("dem", overview_table, session=session)
        raster.finalize_overview_tables(session, "dem", "dem")


if __name__ == "__main__":
    args = parser.parse_args()
    run(args.db_connection, args.input_dir)
