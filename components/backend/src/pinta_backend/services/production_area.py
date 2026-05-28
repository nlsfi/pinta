# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import contextlib
import logging
from collections.abc import Iterator

import sqlalchemy.exc
import sqlmodel
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea

from pinta_backend import db, db_context
from pinta_backend.exceptions import (
    DatabaseUnreachableError,
    ProductionAreaNotFoundError,
)

LOGGER = logging.getLogger(__name__)


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
            production_area: ProductionArea | None = session.exec(
                sqlmodel.select(ProductionArea).where(
                    ProductionArea.id == production_area_id
                )
            ).one_or_none()
            if production_area is None:
                raise ProductionAreaNotFoundError(production_area_id)
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
        raise DatabaseUnreachableError(str(exc)) from exc
