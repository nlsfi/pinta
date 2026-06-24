# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Airflow tasks shared across Pinta DAGs."""

from airflow.sdk import task

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
