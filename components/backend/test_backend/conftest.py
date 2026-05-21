# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import pytest
from fastapi import testclient

from pinta_backend import app


@pytest.fixture
def client() -> testclient.TestClient:
    return testclient.TestClient(app.api)
