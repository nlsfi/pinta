# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from pinta_db.common.base import BaseModel
from qgis._core import (
    QgsAction,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsProject,
    QgsVectorLayer,
)


def get_vector_layer_by_model(model: type[BaseModel]) -> QgsVectorLayer:
    """Get the vector layer for a given model."""
    for layer in QgsProject.instance().mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if layer.dataProvider().uri().table() == model.__tablename__:
            return layer

    message = f"Could not find vector layer for model {model}"
    raise AssertionError(message)


def find_layer_action(
    layer: QgsVectorLayer, short_titles: tuple[str, ...]
) -> QgsAction:
    """Find an action on a layer by its short title."""
    for action in layer.actions().actions():
        if action.shortTitle() in short_titles:
            return action
    msg = f"Action with shortTitle={short_titles} not registered on layer"
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
