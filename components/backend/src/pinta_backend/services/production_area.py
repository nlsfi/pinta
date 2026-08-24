# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import logging
from collections.abc import Iterator

import sqlalchemy.exc
import sqlmodel
from pinta_common import Settings
from pinta_db import constants
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pinta_db_utils import database_utils

from pinta_backend import db, db_context, exceptions

LOGGER = logging.getLogger(__name__)

# Only a finished run may have its database dropped. A run still in flight owns
# the database, and the DAG writes its final status onto the row afterwards.
DELETABLE_PROCESSING_STATUSES = frozenset(
    {ProcessingStatus.COMPLETED, ProcessingStatus.FAILURE}
)


@contextlib.contextmanager
def mark_as_queued(
    production_area_id: str | None,
) -> Iterator[ProductionArea | None]:
    """Mark the production area as queued for the duration of the block.

    Acts as a no-op when `production_area_id` is `None`. Otherwise opens a
    primary-db session (honouring any dev-only db override set on the request
    context), sets the row's status to QUEUED, and on any exception inside the
    wrapped block restores the previous status.
    """
    if production_area_id is None:
        LOGGER.debug("Production area id is None, skipping")
        yield None
        return

    db_name = db_context.get_db_name_override()
    try:
        with db.primary_db_session(db_name) as session:
            production_area = _get_production_area(session, production_area_id)
            LOGGER.debug("Mark production area %s as queued", production_area_id)
            previous_status = production_area.processing_status
            production_area.processing_status = ProcessingStatus.QUEUED
            session.add(production_area)
            session.commit()
            try:
                yield production_area
            except Exception:
                LOGGER.debug(
                    "Set production area %s back to %s",
                    production_area_id,
                    previous_status,
                )
                production_area.processing_status = previous_status
                session.add(production_area)
                session.commit()
                raise
    except sqlalchemy.exc.OperationalError as exc:
        LOGGER.exception("Database error occurred")
        raise exceptions.DatabaseUnreachableError(str(exc)) from exc


def delete_job_database(production_area_id: str) -> str | None:
    """Drop the production area's job database and reset its processing state.

    Returns the name of the dropped database, or None when the production
    area did not have one.
    """
    db_name = db_context.get_db_name_override()
    try:
        with db.primary_db_session(db_name) as session:
            production_area = _get_production_area(session, production_area_id)
            status = production_area.processing_status
            if status not in DELETABLE_PROCESSING_STATUSES:
                raise exceptions.JobDatabaseNotDeletableError(
                    str(production_area.id), status.value
                )
            job_database_name = production_area.database_name
            if job_database_name is not None:
                _drop_job_database(job_database_name)
            _reset_processing_state(session, production_area)
            return job_database_name
    except sqlalchemy.exc.OperationalError as exc:
        LOGGER.exception("Database error occurred")
        raise exceptions.DatabaseUnreachableError(str(exc)) from exc


def _get_production_area(
    session: sqlmodel.Session, production_area_id: str
) -> ProductionArea:
    production_area: ProductionArea | None = session.exec(
        sqlmodel.select(ProductionArea).where(ProductionArea.id == production_area_id)
    ).one_or_none()
    if production_area is None:
        raise exceptions.ProductionAreaNotFoundError(production_area_id)
    return production_area


def _drop_job_database(database_name: str) -> None:
    # The template carries the `job_` prefix under its default name, so the
    # prefix check alone does not protect it.
    if (
        not database_name.startswith(constants.JOB_DATABASE_NAME_PREFIX)
        or database_name == Settings.DB_JOB_TEMPLATE_NAME
    ):
        raise exceptions.JobDatabaseProtectedError(database_name)
    LOGGER.info("Dropping job database %s", database_name)
    try:
        with db.job_db_admin_connection() as connection:
            database_utils.drop_database(connection, database_name)
    except sqlalchemy.exc.OperationalError as exc:
        LOGGER.exception("Job database cluster is not reachable")
        raise exceptions.JobDatabaseUnreachableError(str(exc)) from exc
    except sqlalchemy.exc.DBAPIError as exc:
        LOGGER.exception("Failed to drop job database %s", database_name)
        raise exceptions.JobDatabaseDropFailedError(database_name, str(exc)) from exc


def _reset_processing_state(
    session: sqlmodel.Session, production_area: ProductionArea
) -> None:
    production_area.database_name = None
    production_area.processing_status = ProcessingStatus.NOT_STARTED
    session.add(production_area)
    session.commit()
