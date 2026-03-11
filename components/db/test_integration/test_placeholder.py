# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from pinta_test_utils import db_utils
from sqlalchemy.exc import IntegrityError

from pinta_db.models.temp_model import TemporaryModel, TemporaryModelWithForeignKey
from pinta_db_utils import engine_utils

if TYPE_CHECKING:
    from sqlmodel import Session


@pytest.fixture(scope="session")
def db(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_db(worker_id)
    with engine_utils.get_session(db_utils.get_writer_credentials(db_name)) as session:
        yield session
        session.close()


def test_placeholder(db: "Session"):
    temp_model = TemporaryModel(text="test string", number=1, geom="POINT(0 0)")
    db.add(temp_model)
    temp_model2 = TemporaryModelWithForeignKey(
        number=2, geom="LINESTRING(0 0, 1 1)", temp=temp_model
    )
    db.add(temp_model2)
    db.commit()

    assert temp_model2.temp_id == temp_model.id
    assert temp_model.geom_wkt == "POINT (0 0)"


def test_placeholder2(db: "Session"):
    temp_model2 = TemporaryModelWithForeignKey(number=2, geom="LINESTRING(0 0, 1 1)")
    db.add(temp_model2)
    with pytest.raises(IntegrityError) as excinfo:
        db.commit()
    assert "violates not-null constraint" in str(excinfo.value)
