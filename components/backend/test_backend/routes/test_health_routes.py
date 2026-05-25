# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
from fastapi import testclient


@pytest.mark.parametrize(
    ("accept_language", "expected_language"),
    [
        ("en", "en"),
        ("fi", "fi"),
        ("de", "en"),
    ],
)
def test_health_returns_version_and_language_from_header(
    client: testclient.TestClient,
    accept_language: str,
    expected_language: str,
) -> None:

    response = client.get("/health", headers={"Accept-Language": accept_language})

    assert response.status_code == 200
    response_body = response.json()
    assert response_body["backend_version"]
    assert response_body["parsed_language"] == expected_language
    assert response.headers["Content-Language"] == expected_language
