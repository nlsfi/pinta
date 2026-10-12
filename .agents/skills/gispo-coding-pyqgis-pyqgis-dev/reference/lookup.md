# Where each fact lives

## QGIS checkout (`$QGIS_SRC`)

| Path | Holds | Use it for |
|---|---|---|
| `src/core/`, `src/gui/`, `src/analysis/`, `src/3d/`, `src/server/` | C++ headers and sources of the public API | what a method does; Doxygen text (`\brief`, `\since`, `\deprecated`, `\note`); the `SIP_*` annotations |
| `src/core/qgis.h` | the `Qgis` namespace with all scoped enums | enum names and their `\since` |
| `src/core/qgis_sip.h` | the `SIP_*` macros, with comments | what each annotation means |
| `src/app/` | the QGIS desktop application itself | how QGIS does something (dialogs, map tools, editing) |
| `python/core/auto_generated/**/*.sip.in` (also `gui`, `analysis`) | the Python binding, generated from the headers | exactly what Python sees: names, `/Transfer/`, `%MethodCode`, missing methods |
| `python/PyQt6/core/auto_generated/` | the same for the Qt 6 build | differences between the two builds |
| `python/PyQt/PyQt/*.py.in` | source of the `qgis.PyQt` shim | which names are re-exported for Qt 5 / 6 compatibility |
| `python/custom_widgets/qgis_customwidgets.py` | uic mapping for QGIS widgets in `.ui` files | `.ui` custom widget headers |
| `python/plugins/` | bundled Python plugins (processing, db_manager, MetaSearch) | real PyQGIS usage examples |
| `tests/src/python/` | Python unit tests of the API | usage examples; expected behaviour |
| `resources/` | icons, default styles, `qgis_global_settings.ini` | icon names for `QgsApplication.getThemeIcon` |

The docstrings you see in Python, and the pyqgis web docs, are generated from the
Doxygen comments in the headers. The header is the original.

## QGIS 4 checkout (`$QGIS4_SRC`)

Same layout, two differences: the binding files live only under
`python/PyQt6/core/auto_generated/` (there is no `python/core/` any more), and API that was
`\deprecated` in 3.x may be gone. `find_source.py PATTERN --qgis4` searches it;
`api_doc.py` uses it automatically when run under a QGIS 4 Python. The migration script is
`scripts/pyqt5_to_pyqt6/pyqt5_to_pyqt6.py` (see `../../qgis4-migration/reference/migration.md`).

## QGIS documentation checkout (`$QGIS_DOCS_SRC`)

`docs/pyqgis_developer_cookbook/` is the PyQGIS developer cookbook, deployed at
`https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/`. It is the official how-to:
plugin structure and `metadata.txt` (`plugins/plugins.rst`), releasing (`plugins/releasing.rst`),
IDE debugging, tasks, vector layers, canvas and map tools, settings, expressions, processing,
network access, `cheat_sheet.rst`. reStructuredText; code samples are tested against the QGIS
release the branch documents (`master` = current). `find_source.py "text" --docs` searches it;
`--path docs/user_manual` widens it to the user manual.

## Qt checkout (`$QTBASE_SRC` for Qt 5, `$QTBASE6_SRC` for Qt 6)

| Path | Holds |
|---|---|
| `src/corelib/` (`kernel`, `io`, `tools`, `text`, `thread`, `itemmodels`, `serialization`) | QObject, QVariant, QSettings, QThread, item models, JSON, XML streams |
| `src/gui/` (`kernel`, `painting`, `text`, `image`) | QAction (Qt 6), QPainter, QFont, QImage, events |
| `src/widgets/` (`kernel`, `widgets`, `itemviews`, `dialogs`, `graphicsview`, `styles`) | QWidget, layouts, all widgets, views, dialogs |
| `src/network/`, `src/xml/`, `src/sql/`, `src/printsupport/` | the other modules |
| `src/tools/uic/ui4.h` | the `.ui` file model |

The documentation text is in the `.cpp` files as `/*! \fn ... */` and `\brief` comments,
not in the headers. `\since 5.x` says when a method appeared. Class `QFoo` is usually in
`qfoo.h` / `qfoo.cpp`. Exceptions: `QVBoxLayout` and `QHBoxLayout` in `qboxlayout.*`, the
`Qt::` namespace in `qnamespace.h` and `qnamespace.qdoc`.

## PyQt sip bindings (`$PYQT_BINDINGS`, `$PYQT6_BINDINGS`)

One `.sip` file per Qt header, for example `QtWidgets/qabstractitemview.sip`. Shows
`/Transfer/`, `/TransferThis/`, `/KeepReference/`, `/Factory/` on every argument, and
`%MethodCode` where PyQt does something special. Found automatically next to the PyQt
package of `$QGIS_PYTHON`; `pyqgis_env.py` prints the path. Some Linux distributions
ship it in a separate dev package.

## SIP annotation cheat sheet

| In a QGIS header | In a .sip file | Meaning |
|---|---|---|
| `SIP_TRANSFER` | `/Transfer/` | ownership goes to C++ |
| `SIP_TRANSFERTHIS` | `/TransferThis/` | the new object is owned by this parent argument |
| `SIP_TRANSFERBACK` | `/TransferBack/` | ownership returns to Python |
| `SIP_FACTORY` | `/Factory/` | the returned object is new and Python-owned |
| `SIP_KEEPREFERENCE` | `/KeepReference/` | Python keeps the argument alive together with the owner |
| nothing, on a pointer argument | nothing | C++ stores a raw pointer; the caller must keep the Python object alive |
| `SIP_OUT`, `SIP_INOUT` | `/Out/`, `/In,Out/` | a C++ output argument becomes (part of) the Python return value, often a tuple |
| `SIP_SKIP` | (absent) | not available in Python |
| `SIP_PYNAME(x)` | `/PyName=x/` | different name in Python |
| `SIP_PYARGREMOVE` | (absent) | the argument does not exist in Python |
| `SIP_DEPRECATED` | `/Deprecated/` | warns on use; gone in the next major |
| `SIP_HOLDGIL`, `SIP_RELEASEGIL` | `/HoldGIL/`, `/ReleaseGIL/` | threading behaviour |
| `SIP_THROW(...)` | `throw(...)` | the C++ exception becomes a Python exception |
| `%MethodCode` block in the .sip | | hand-written Python behaviour: raises, returns tuples, converts |

The full list with explanations is in `$QGIS_SRC/src/core/qgis_sip.h`.

## Docstring format (what `api_doc.py` parses)

```
getFeatures(self, request: QgsFeatureRequest = QgsFeatureRequest()) -> QgsFeatureIterator

Queries the layer for features ...
```

One signature line per overload, a blank line, then the Doxygen text. Signals carry the
doc too; their C++ signature is in `Class.signal.signatures`.

## Grep recipes

```
python find_source.py "SIP_TRANSFER" --h --path src/gui/qgsmapcanvas.h              # ownership on one class
python find_source.py "since QGIS 3\.3[0-9]" --h --path src/core/qgis.h             # what arrived when
python find_source.py "deprecated" --h --path src/core/vector                       # what to avoid
python find_source.py "QgsTask\(" --py --path python/plugins --path tests/src/python  # usage examples
python find_source.py "%MethodCode" --sip --path python/core/auto_generated/vector   # Python-only behaviour
python find_source.py "void QWidget::setParent" --qt --cpp -C 12                     # Qt docs + code
python find_source.py "KeepReference" --pyqt --path QtWidgets                        # what PyQt keeps alive
```

`git -C "$QGIS_SRC" grep -n PATTERN -- src/core` works as well. The script only adds
default paths and root lookup.

## Web fallbacks (when a clone is missing)

- PyQGIS: `https://qgis.org/pyqgis/3.44/core/QgsVectorLayer.html` (module dir is `core`, `gui` or `analysis`; the version is in the path)
- QGIS C++ API per version: `https://api.qgis.org/api/3.44/classQgsVectorLayer.html` (older: `https://api.qgis.org/api/3.28/`)
- PyQGIS cookbook: `https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/`
- Qt 5: `https://doc.qt.io/qt-5/qwidget.html`; Qt 6: `https://doc.qt.io/qt-6/qwidget.html` (lowercase class name)
- PyQt reference: `https://www.riverbankcomputing.com/static/Docs/PyQt5/api/qtwidgets/qwidget.html` and the same under `Docs/PyQt6/`
- Qt 5 to 6 porting guide: `https://doc.qt.io/qt-6/portingguide.html`

## Checking an older QGIS version

Shallow clones have no history. To see whether something exists in, say, 3.28: read the
`\since` line in the header, or fetch that branch without history:

```
git -C "$QGIS_SRC" fetch --depth 1 origin release-3_28
git -C "$QGIS_SRC" show FETCH_HEAD:src/core/vector/qgsvectorlayer.h | grep -n methodName
```

or open `https://api.qgis.org/api/3.28/`.
