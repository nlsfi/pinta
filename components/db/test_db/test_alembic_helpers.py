# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


import typing

import pytest

from pinta_db_utils import alembic_helpers

if typing.TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


@pytest.fixture
def autogen_context(mocker: "MockerFixture") -> "MagicMock":
    context = mocker.MagicMock()
    context.imports = mocker.MagicMock()
    return context


def test_render_item_replaces_srid(
    mocker: "MockerFixture",
    autogen_context: "MagicMock",
) -> None:
    mocker.patch(
        "pinta_db_utils.alembic_helpers.geoalchemy2.alembic_helpers.render_item",
        return_value="geoalchemy2.types.Geometry(geometry_type='POINT', srid=3067)",
    )

    result = alembic_helpers.render_item("type", object(), autogen_context)

    assert "srid=SRID" in result
    assert "srid=3067" not in result


def test_render_item_preserves_other_attributes(
    mocker: "MockerFixture",
    autogen_context: "MagicMock",
) -> None:
    mocker.patch(
        "pinta_db_utils.alembic_helpers.geoalchemy2.alembic_helpers.render_item",
        return_value=(
            "Geometry("
            "geometry_type='POINT', srid=3067, dimension=2, spatial_index=True)"
        ),
    )

    result = alembic_helpers.render_item("type", object(), autogen_context)

    assert "srid=SRID" in result
    assert "dimension=2" in result
    assert "spatial_index=True" in result


def test_render_item_adds_import(
    mocker: "MockerFixture",
    autogen_context: "MagicMock",
) -> None:
    mocker.patch(
        "pinta_db_utils.alembic_helpers.geoalchemy2.alembic_helpers.render_item",
        return_value="Geometry(geometry_type='POINT', srid=3067)",
    )

    alembic_helpers.render_item("type", object(), autogen_context)

    autogen_context.imports.add.assert_called_once_with("from pinta_db.env import SRID")


def test_render_item_returns_false_for_non_geometry(
    mocker: "MockerFixture",
    autogen_context: "MagicMock",
) -> None:
    mocker.patch(
        "pinta_db_utils.alembic_helpers.geoalchemy2.alembic_helpers.render_item",
        return_value=False,
    )

    result = alembic_helpers.render_item("type", object(), autogen_context)

    assert result is False
    autogen_context.imports.add.assert_not_called()


@pytest.mark.parametrize("srid", [4326, 3067, 25832])
def test_render_item_replaces_any_srid(
    mocker: "MockerFixture",
    autogen_context: "MagicMock",
    srid: int,
) -> None:
    mocker.patch(
        "pinta_db_utils.alembic_helpers.geoalchemy2.alembic_helpers.render_item",
        return_value=f"Geometry(geometry_type='POINT', srid={srid})",
    )

    result = alembic_helpers.render_item("type", object(), autogen_context)

    assert result == "Geometry(geometry_type='POINT', srid=SRID)"
