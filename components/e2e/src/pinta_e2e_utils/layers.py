# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_db.common.base import BaseModel
from pinta_db_utils import model_utils
from qgis._core import (
    QgsAction,
    QgsDataSourceUri,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)


def _uri_matches_model(uri: QgsDataSourceUri, model: type[BaseModel]) -> bool:
    schema, table = model_utils.schema_and_table(model)
    return uri.table() == table and uri.schema() == schema


def get_vector_layer_by_model(model: type[BaseModel]) -> QgsVectorLayer:
    """Get the vector layer for a given model."""
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and _uri_matches_model(
            layer.dataProvider().uri(), model
        ):
            return layer

    message = f"Could not find vector layer for model {model}"
    raise AssertionError(message)


def get_raster_layer_by_model(model: type[BaseModel]) -> QgsRasterLayer:
    """Get the raster layer for a given model."""
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsRasterLayer) and _uri_matches_model(
            QgsDataSourceUri(layer.source()), model
        ):
            return layer

    message = f"Could not find raster layer for model {model}"
    raise AssertionError(message)


def find_layer_action(layer: QgsVectorLayer, short_title: str) -> QgsAction:
    """Find an action on a layer by its short title."""
    for action in layer.actions().actions():
        if action.shortTitle() == short_title:
            return action
    msg = f"Action with shortTitle={short_title} not registered on layer"
    raise AssertionError(msg)


def run_layer_action(
    layer: QgsVectorLayer, action: QgsAction, feature: QgsFeature
) -> None:
    """Run an action on a layer."""
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    context.setFeature(feature)

    # QgsAction.run() cannot be used directly, replace the placeholders in the command
    substituted_command = QgsExpression.replaceExpressionText(action.command(), context)
    # And run it with exec
    exec(substituted_command, {})  # noqa: S102
