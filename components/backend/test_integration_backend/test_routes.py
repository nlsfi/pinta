# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


import httpx
import pytest


@pytest.mark.parametrize(
    ("accept_language", "expected_language"),
    [
        ("en", "en"),
        ("fi", "fi"),
        ("not a valid language", "en"),
    ],
)
def test_health_returns_version_and_selected_language(
    api: httpx.Client,
    accept_language: str,
    expected_language: str,
):
    response = api.get(
        "/health",
        headers={"Accept-Language": accept_language},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["backend_version"]
    assert payload["parsed_language"] == expected_language
