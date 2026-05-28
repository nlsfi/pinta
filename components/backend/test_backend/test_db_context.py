# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import types

import pytest
from pytest_mock import MockerFixture

from pinta_backend import db_context


@pytest.fixture
def dev_mode(mocker: MockerFixture) -> None:
    mocker.patch.object(
        db_context.settings,
        "get_settings",
        return_value=types.SimpleNamespace(development_mode=True),
    )


@pytest.fixture
def production_mode(mocker: MockerFixture) -> None:
    mocker.patch.object(
        db_context.settings,
        "get_settings",
        return_value=types.SimpleNamespace(development_mode=False),
    )


def test_set_and_get_db_name_override_in_dev_mode(dev_mode: None) -> None:
    db_context.set_db_name_override("pinta_test_gw0")

    assert db_context.get_db_name_override() == "pinta_test_gw0"


def test_get_db_name_override_defaults_to_none() -> None:
    db_context.set_db_name_override(None)

    assert db_context.get_db_name_override() is None


def test_set_db_name_override_ignored_outside_dev_mode(production_mode: None) -> None:
    db_context.set_db_name_override("pinta_test_gw0")

    assert db_context.get_db_name_override() is None


@pytest.mark.parametrize("db_name", ["pinta;drop", "pinta-test", "bad name", ""])
def test_set_db_name_override_rejects_invalid_names(
    dev_mode: None, db_name: str
) -> None:
    db_context.set_db_name_override(db_name)

    assert db_context.get_db_name_override() is None
