# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Airflow tasks shared across Pinta DAGs."""

from airflow.sdk import TriggerRule, task

from pinta_dags import config


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def get_database_name(
    connection_uri: str,
    production_area_id: str,
) -> str:
    """Return the job database name set on the given production area."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.primary_db.models.management import ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if area_in_db is None or area_in_db.database_name is None:
            msg = f"Production area {production_area_id} has no database name set"
            raise ValueError(msg)
        return area_in_db.database_name


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def find_production_area_tile_paths(
    connection_uri: str,
    production_area_id: str,
) -> list[str]:
    """Return the source file paths of the production area's point cloud tiles."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.primary_db.models.management import ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if not area_in_db:
            return []
        return [tile.file_path for tile in area_in_db.tiles]


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def find_production_area_tile_geometries(
    connection_uri: str,
    production_area_id: str,
) -> list[str]:
    """Return the geometries (as WKT) of the production area's point cloud tiles."""
    import sqlalchemy
    import sqlmodel
    from geoalchemy2.shape import to_shape
    from pinta_db.primary_db.models.management import ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if not area_in_db:
            return []
        return [to_shape(tile.geom).wkt for tile in area_in_db.tiles]


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def find_production_area_geometry(
    connection_uri: str,
    production_area_id: str,
) -> str:
    """Return the geometry (as WKT) of the production area itself."""
    import sqlalchemy
    import sqlmodel
    from geoalchemy2.shape import to_shape
    from pinta_db.primary_db.models.management import ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if area_in_db is None:
            msg = f"Production area {production_area_id} not found"
            raise ValueError(msg)
        return to_shape(area_in_db.geom).wkt


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def find_dirty_update_areas(
    connection_uri: str,
) -> list[dict[str, str]]:
    """Return the id of every dirty update area."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.job_db.models.user import UpdateArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        update_areas = session.exec(
            sqlmodel.select(UpdateArea).where(sqlmodel.col(UpdateArea.dirty).is_(True))
        ).all()
        return [{"update_area_id": str(area.id)} for area in update_areas]


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def find_update_area_geometries(
    connection_uri: str,
) -> list[str]:
    """Return the geometry (as WKT) of every update area."""
    import sqlalchemy
    import sqlmodel
    from geoalchemy2.shape import to_shape
    from pinta_db.job_db.models.user import UpdateArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        update_areas = session.exec(sqlmodel.select(UpdateArea)).all()
        return [to_shape(area.geom).wkt for area in update_areas]


@task
def build_job_connection_uri_task(
    base_uri: str,
    database_name: str,
) -> str:
    """Return ``base_uri`` with its database path replaced by ``database_name``."""
    return config.build_job_connection_uri(base_uri, database_name)


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def initialize_dem_tables(
    connection_uri: str,
    schema: str,
    table: str,
    staging_tables: int,
) -> None:
    """Initialize the raster and overview tables (plus staging) for a DEM table."""
    import sqlalchemy
    import sqlmodel
    from pinta_db_utils.postgis import raster

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        raster.initialize_raster_table(
            session,
            schema,
            table,
            staging_tables,
        )
        raster.initialize_overview_tables(
            session,
            schema,
            table,
            staging_tables,
        )


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def merge_dem_staging_tables(
    connection_uri: str, schema: str, table: str, staging_tables: int
) -> None:
    """Merge staging tables into the target DEM table and its overview tables."""
    import sqlalchemy
    import sqlmodel
    from pinta_db_utils.postgis import raster

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        raster.merge_staging_tables(
            schema,
            table,
            staging_tables=staging_tables,
            session=session,
        )
        for level in raster.DEFAULT_OVERVIEW_LEVELS:
            overview_table = raster.OVERVIEW_TABLE_NAME.format(
                level=level, table_name=table
            )
            raster.merge_staging_tables(
                schema,
                overview_table,
                staging_tables=staging_tables,
                session=session,
            )


@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)
def set_processing_status_started(connection_uri: str, production_area_id: str) -> None:
    """Mark the production area as processing started."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if area_in_db:
            area_in_db.processing_status = ProcessingStatus.STARTED
            session.commit()


@task.docker(
    **config.PINTA_CONTAINER_TASK_ARGS,
    trigger_rule=TriggerRule.NONE_FAILED,
)
def set_processing_status_completed(
    connection_uri: str, production_area_id: str
) -> None:
    """Mark the production area as processing completed when nothing failed."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if area_in_db:
            area_in_db.processing_status = ProcessingStatus.COMPLETED
            session.commit()


@task.docker(
    **config.PINTA_CONTAINER_TASK_ARGS,
    trigger_rule=TriggerRule.ONE_FAILED,
)
def set_processing_status_failed(connection_uri: str, production_area_id: str) -> None:
    """Mark the production area as processing failed when any upstream failed."""
    import sqlalchemy
    import sqlmodel
    from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea

    engine = sqlalchemy.create_engine(connection_uri)
    with sqlmodel.Session(engine) as session:
        area_in_db = session.exec(
            sqlmodel.select(ProductionArea).where(
                ProductionArea.id == production_area_id
            )
        ).first()
        if area_in_db:
            area_in_db.processing_status = ProcessingStatus.FAILURE
            session.commit()
