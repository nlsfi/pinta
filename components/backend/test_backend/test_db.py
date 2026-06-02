# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from unittest import mock

from pytest_mock import MockerFixture

from pinta_backend import db


def _mock_settings(mocker: MockerFixture) -> None:
    mocker.patch.object(
        db.settings,
        "get_settings",
        return_value=mock.Mock(
            primary_db_uri="postgresql://u:p@h:5432/pinta",
            primary_db_uri_for=lambda name: f"postgresql://u:p@h:5432/{name}",
        ),
    )


def test_primary_db_session_targets_override_database(mocker: MockerFixture) -> None:
    _mock_settings(mocker)
    create_engine = mocker.patch.object(db.sqlalchemy, "create_engine")
    mocker.patch.object(db.sqlmodel, "Session")

    with db.primary_db_session("pinta_test_gw0"):
        pass

    assert create_engine.call_args.args[0].endswith("/pinta_test_gw0")


def test_primary_db_session_defaults_to_configured_database(
    mocker: MockerFixture,
) -> None:
    _mock_settings(mocker)
    create_engine = mocker.patch.object(db.sqlalchemy, "create_engine")
    mocker.patch.object(db.sqlmodel, "Session")

    with db.primary_db_session():
        pass

    assert create_engine.call_args.args[0].endswith("/pinta")
