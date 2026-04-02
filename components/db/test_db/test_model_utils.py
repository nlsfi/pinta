# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
from sqlmodel import SQLModel

from pinta_db.models.management import PointCloudTile, ProductionArea
from pinta_db_utils import model_utils


def test_geometry_type_returns_geometry_type_from_model() -> None:
    result = model_utils.geometry_type(ProductionArea, "geom")

    assert result == "MULTIPOLYGON"


def test_geometry_type_with_default_field_name() -> None:
    result = model_utils.geometry_type(ProductionArea)

    assert result == "MULTIPOLYGON"


@pytest.mark.parametrize(
    ("model_class", "expected_key_column"),
    [
        (ProductionArea, "id"),
        (PointCloudTile, "id"),
    ],
)
def test_primary_key_column_returns_primary_key_from_model(
    model_class: type[SQLModel], expected_key_column: str
) -> None:
    result = model_utils.primary_key_column(model_class)

    assert result == expected_key_column


@pytest.mark.parametrize(
    ("model_class", "expected_geom_column"),
    [
        (ProductionArea, "geom"),
        (PointCloudTile, "geom"),
    ],
)
def test_geometry_column_returns_geometry_column_from_model(
    model_class: type[SQLModel], expected_geom_column: str
) -> None:
    result = model_utils.geometry_column(model_class)

    assert result == expected_geom_column
