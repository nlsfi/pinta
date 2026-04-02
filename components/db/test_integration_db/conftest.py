# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing
from collections.abc import Iterator

import pytest
from pinta_test_utils import xdist_utils

from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils

if typing.TYPE_CHECKING:
    from sqlmodel import Session


@pytest.hookimpl
def pytest_xdist_auto_num_workers(config: "pytest.Config"):
    return xdist_utils.get_number_of_workers(config)


@pytest.fixture
def db(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_db(worker_id)
    with engine_utils.get_session(db_utils.get_writer_credentials(db_name)) as session:
        yield session
        session.close()


@pytest.fixture
def processing_worker_db(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_db(worker_id)
    with engine_utils.get_session(
        db_utils.get_processing_worker_credentials(db_name)
    ) as session:
        yield session
        session.close()
