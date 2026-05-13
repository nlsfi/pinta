# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import typing

from pinta_db_utils.postgis import constraints

if typing.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_add_raster_constraints_returns_when_session_user_is_not_owner(
    mocker: "MockerFixture",
) -> None:
    session = mocker.MagicMock()
    make_empty_raster = mocker.patch(
        "pinta_db_utils.postgis.constraints._make_empty_raster"
    )
    add_default_raster_constraints = mocker.patch(
        "pinta_db_utils.postgis.constraints._add_default_raster_constraints"
    )
    mocker.patch(
        "pinta_db_utils.postgis.utils.session_user_owns_table",
        return_value=False,
    )

    make_empty_raster.assert_not_called()
    add_default_raster_constraints.assert_not_called()
    session.exec.assert_not_called()


def test_add_raster_constraints_runs_when_session_user_is_owner(
    mocker: "MockerFixture",
) -> None:
    session = mocker.MagicMock()
    mocker.patch("pinta_db_utils.postgis.constraints._make_empty_raster")
    add_default_raster_constraints = mocker.patch(
        "pinta_db_utils.postgis.constraints._add_default_raster_constraints"
    )
    mocker.patch(
        "pinta_db_utils.postgis.utils.session_user_owns_table",
        return_value=True,
    )

    constraints.add_raster_constraints(session, "some_schema", "some_table", 2)

    add_default_raster_constraints.assert_called_once_with(
        session, "some_schema", "some_table"
    )
    session.exec.assert_called_once()


def test_add_constraint_extent_returns_when_session_user_is_not_owner(
    mocker: "MockerFixture",
) -> None:
    session = mocker.MagicMock()
    mocker.patch(
        "pinta_db_utils.postgis.utils.session_user_owns_table",
        return_value=False,
    )
    constraints.add_constraint_extent(session, "some_schema", "some_table")
    session.exec.assert_not_called()


def test_add_constraint_regular_blocking_returns_when_session_user_is_not_owner(
    mocker: "MockerFixture",
) -> None:
    session = mocker.MagicMock()
    add_constraint_from_sql = mocker.patch(
        "pinta_db_utils.postgis.constraints._add_constraint_from_sql"
    )
    mocker.patch(
        "pinta_db_utils.postgis.utils.session_user_owns_table",
        return_value=False,
    )

    constraints.add_constraint_regular_blocking(
        session, "some_schema", "some_table", 256
    )

    add_constraint_from_sql.assert_not_called()
