# PyQt / PyQGIS pitfalls

Facts here were checked against QGIS 3.44 / Qt 5.15 / PyQt 5.15 and QGIS 4.2 / Qt 6.11 / PyQt 6.
Re-check with `api_doc.py` and the SIP files when in doubt; version numbers move.

## 1. Who owns the object? (the number one crash cause)

A Python object that wraps a C++ object can be deleted from either side.

- If C++ deletes it first, Python raises `RuntimeError: wrapped C/C++ object of type X has been deleted`.
- If Python garbage-collects a wrapper that C++ still uses, QGIS crashes with no traceback.

The rule for each call is written in the SIP annotation. Look it up before you hand an
object to C++ (SKILL.md sections 1 and 2); the full cheat sheet is in `lookup.md`. The two
that matter most:

- `SIP_TRANSFER` (`/Transfer/` in the .sip file): C++ takes ownership. Reuse or delete from Python is a crash.
- No annotation on a pointer argument: C++ only stores a raw pointer. **You** must keep the Python object alive.

Checked examples (QGIS 3.44 headers):

- `QgsMapCanvas.setMapTool(tool)` and `QgsMapCanvas.setLayers(layers)` have no annotation. Keep the tool and the layers on `self`.
- `QgsProject.addMapLayer(s)`, `QgsTaskManager.addTask(task)`, `QgsMessageBar.pushWidget(widget)` and `QgsProject.setBadLayerHandler(handler)` are `SIP_TRANSFER`. C++ owns them after the call.
- `QAbstractItemView.setModel(model)` is `/KeepReference/` in PyQt5. The view keeps the model alive.

Habits that avoid the crashes:

- Give every QObject a parent, or store it on `self`. A dialog created without a parent and shown with `show()` disappears when the local variable dies.
- A `QgsVectorLayer` you create in Python is owned by Python until you add it to a project or a `QgsMapLayerStore`. If a canvas still shows it when Python drops it, QGIS crashes.
- Layouts re-parent the widgets you add. Widgets created with a parent are owned by the parent.
- Before touching an object that may be gone: `from qgis.PyQt import sip` and `if sip.isdeleted(obj): return`.
- `QgsRubberBand`, `QgsVertexMarker` and other canvas items belong to the canvas scene. Remove them with `canvas.scene().removeItem(item)`, then drop your reference.
- Do not keep `QgsFeatureIterator` objects open longer than needed; they hold provider resources. Do not iterate while editing the same layer.

## 2. Signals and slots

- Get the real signature from the live class: `QgsVectorLayer.featureAdded.signatures` gives `('featureAdded(QgsFeatureId)',)`. The stubs mistype these.
- Overloaded signals: pick one with `signal[type].connect(slot)`. Qt 5.15 and Qt 6 dropped several `[str]` overloads. Use `QComboBox.currentTextChanged`, not `currentIndexChanged[str]`.
- A slot may take fewer arguments than the signal sends. PyQt drops the extra ones from the end.
- `@pyqtSlot(...)` is optional. If you use it, the types must match the signal exactly, or the slot is never called.
- An exception inside a slot: QGIS shows its Python error dialog and the rest of the slot does not run. State may be half-updated. Keep slots short; wrap risky work and log with `QgsMessageLog.logMessage(msg, "PluginName", Qgis.MessageLevel.Warning)`.
- `signal.disconnect(slot)` raises `TypeError` when it was not connected. Guard it, or keep the connection object that `connect()` returns.
- Silence a widget while you set it: `with QSignalBlocker(widget): widget.setValue(x)` (works on both PyQts), or `widget.blockSignals(True)`.
- Lambdas that capture `self` keep `self` alive until disconnected. In loops bind the loop variable: `lambda checked=False, x=x: ...`. The first parameter of `clicked` is `checked`.
- Signals crossing threads are queued automatically when the receiver lives in the main thread. Pass Python objects with `pyqtSignal(object)`. Do not put `QVariant` in signal definitions.

## 3. Threads and tasks

- `QgsTask.run()` runs in a worker thread. No GUI, no `iface`, no layer edits, no `QgsProject` changes there. Return `True` or `False`; `finished(result)` then runs in the main thread.
- Read features in a task through a `QgsVectorLayerFeatureSource(layer)` created in the main thread, not through the layer itself.
- Report progress with `self.setProgress(pct)`. Check `self.isCanceled()` in loops.
- Add the task with `QgsApplication.taskManager().addTask(task)`; C++ owns it from then on. Keep a reference on `self` so you can read its state, and do not touch it after it finished and was deleted.
- Exceptions in `run()` disappear. Catch them, store the message on the task, and show it in `finished()`.
- Network in a task: `QgsBlockingNetworkRequest`. In the main thread: `QgsNetworkAccessManager` with signals.

## 4. NULL, QVariant and attribute values

- Qt 5: a null attribute comes back as `NULL`, a `QVariant`. `value == NULL` is True and `value == None` is True, but `value is None` is False.
- Qt 6: the same value is plain `None`; `NULL` itself is `None`.
- So test nulls with `QgsVariantUtils.isNull(value)` (QGIS 3.28 and newer) or `value == NULL`. Never `is None` in code that must run on Qt 5.
- Set a null with `feature.setAttribute("f", NULL)` on both.
- `QVariant.Type` (the enum class) does not exist on Qt 6. `QVariant.Int`, `QVariant.String` and friends still resolve to `QMetaType.Type` members on both (checked on 3.44 and 4.2), and `QgsField.type()` returns `QMetaType.Type` on both. Write `QMetaType.Type.Int` in new code.

## 5. Other things that bite

- `iface` exists only inside the QGIS desktop application. Reach it inside functions, from the `iface` handed to `classFactory`, so library modules import headless. In tests use the official mock `qgis.testing.mocked.get_iface()` (conftest example: `qt5-qt6.md`, Testing both).
- `QgsProject.instance()` is a singleton. In tests it persists between tests unless you clear it (call `QgsProject.instance().clear()` in the test setup).
- Editing: `layer.startEditing()` plus `commitChanges()` goes through the edit buffer (undo, signals). `layer.dataProvider().addFeatures()` bypasses it: no undo, no `featureAdded`, and the layer may need `reload()` or `triggerRepaint()`.
- Feature iterators become stale when the layer changes. Collect ids first if you edit while iterating.
- Modal dialogs: `dialog.exec()` blocks and returns `QDialog.DialogCode.Accepted`. `dialog.show()` returns at once, so keep the dialog on `self`.
- Icons: `QgsApplication.getThemeIcon("/mActionAdd.svg")` for QGIS icons (names in `$QGIS_SRC/resources/images/themes/default`). Plugin icons: build the path from `__file__`, or compile a `resources_rc.py`; uic needs that module when a `.ui` file lists `<resources>`.
- Translations: `QCoreApplication.translate("Context", "text")` or the plugin's own `tr()` helper.
- Settings: `QgsSettings` wraps `QSettings` and also reads QGIS global settings. Give a default and a `type=`.
- Processing in tests needs the registry: `from processing.core.Processing import Processing` then `Processing.initialize()`.

## 6. Symptom to likely cause

| Symptom | Look at |
|---|---|
| `RuntimeError: wrapped C/C++ object of type X has been deleted` | C++ deleted it: parent died, task finished, dialog closed. Check ownership; guard with `sip.isdeleted`. |
| QGIS closes with no traceback | Python released an object C++ still used: map tool, layer in a canvas, model. Store it on `self`. |
| A slot never runs | `@pyqtSlot` type mismatch, wrong overload, or the sender was garbage-collected. |
| `TypeError` when emitting a signal | Declared a C++ type in `pyqtSignal` and sent something else. Use `object` or the right type. |
| Works in QGIS, fails in tests | `iface` used at import time, or singleton state left by an earlier test. |
| Works on Qt 5, fails on Qt 6 | See `qt5-qt6.md`: unscoped enum, `exec_`, `QRegExp`, `QVariant.Type`, `is None`. |
