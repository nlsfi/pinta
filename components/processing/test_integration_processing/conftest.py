# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import typing
from collections.abc import Iterator

import pytest
from pinta_common import env
from pinta_db_test_utils import db_utils
from pinta_db_utils import engine_utils
from pinta_test_utils import pinta_utils

if typing.TYPE_CHECKING:
    from sqlmodel import Session


LASTOOLS_BIN_DIR = pinta_utils.get_project_root() / "external" / "LAStools" / "bin"


@pytest.fixture
def lastools_in_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prepend external/LAStools/bin to PATH and enable demo mode.

    Skips the test when the binaries are not installed at the expected location.
    """
    if not LASTOOLS_BIN_DIR.exists():
        pytest.skip(f"LAStools binaries not found at {LASTOOLS_BIN_DIR}")

    monkeypatch.setenv(
        "PATH", f"{LASTOOLS_BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
    )
    monkeypatch.setattr(env, "LASTOOLS_DEMO_MODE", "true")


@pytest.fixture
def session(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_primary_db(worker_id)
    with engine_utils.get_session(
        db_utils.get_primary_writer_credentials(db_name)
    ) as session:
        yield session
        session.close()


@pytest.fixture
def processing_worker_session(worker_id: str) -> Iterator["Session"]:
    db_name = db_utils.create_primary_db(worker_id)
    with engine_utils.get_session(
        db_utils.get_primary_processing_worker_credentials(db_name)
    ) as session:
        yield session
        session.close()
