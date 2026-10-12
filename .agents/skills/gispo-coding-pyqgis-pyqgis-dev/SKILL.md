---
name: pyqgis-dev
description: Develop, review, debug and test QGIS Python plugins (PyQGIS with PyQt5 or PyQt6). Use whenever a task touches QGIS plugin code, the qgis.core / qgis.gui API, PyQt or Qt classes, Qt 5 vs Qt 6 compatibility, or Qt Designer .ui files. Verifies every API fact against the trust order (live QGIS Python first, stubs last) with bundled scripts.
---

# PyQGIS development

QGIS is C++. Python sees it through SIP-generated bindings; PyQt does the same for Qt.
Type stubs (`_core.pyi`, `PyQt5-stubs`) are approximations with known errors.
So: **verify every API claim against the trust order (section 1) before you state it,
and say which level confirmed it.**

Scripts live in `scripts/` next to this file; each prints options and examples with
`--help`. Reference notes live in `reference/`.

## 0. Once per session: find the sources

```
python <skill-dir>/scripts/pyqgis_env.py
```

`<skill-dir>` is the directory that holds this SKILL.md
(if unknown: `find ~/.claude/skills .claude/skills -name pyqgis_env.py`).
The script reads these environment variables, auto-detects whatever is unset, and prints
what it found, the clone command for each missing source, and a config block for
`.claude/settings.local.json`:

| Variable | Needed for |
|---|---|
| `QGIS_PYTHON` | everything below; the Python that imports `qgis.core` (QGIS 3 when both exist) |
| `QGIS4_PYTHON` | QGIS 4 / Qt 6 cross-checks; an optional second Python |
| `QGIS_SRC` / `QGIS4_SRC` | ownership rules, behaviour, `\since` (QGIS 3.x / 4.x checkout) |
| `QGIS_DOCS_SRC` | the PyQGIS developer cookbook: how-to, plugin structure, `metadata.txt` |
| `QTBASE_SRC` / `QTBASE6_SRC` | Qt 5 / Qt 6 behaviour and docs |
| `PYQT_BINDINGS` / `PYQT6_BINDINGS` | Qt ownership rules; found automatically |

QGIS 3 always runs on Qt 5 / PyQt5, QGIS 4 always on Qt 6 / PyQt6. Tell the user what is
missing and carry on with what exists; web docs replace a missing clone.

## 1. Trust order for API facts

1. **Live QGIS Python.** What exists, real signatures, real signal types.
   `"$QGIS_PYTHON" <skill-dir>/scripts/api_doc.py QgsVectorLayer.featureAdded`
2. **SIP binding files.** Ownership (`SIP_TRANSFER`, `/Transfer/`, `/KeepReference/`),
   skipped or renamed methods, Python-only behaviour (`%MethodCode`).
   `$QGIS_SRC/python/**/*.sip.in` and `$PYQT_BINDINGS/**/*.sip`.
3. **C++ headers and .cpp.** What it does, `\since`, `\deprecated`, the Doxygen text
   (the web docs are generated from these).
4. **Web docs.** `https://qgis.org/pyqgis/<major.minor>/`, `https://doc.qt.io/qt-5/<class>.html`,
   `https://doc.qt.io/qt-6/<class>.html`. Fine when a clone is missing.
5. **Stubs.** A hint for spelling only. Known problems: the QGIS `.pyi` files mistype Qt
   signals; `PyQt5-stubs` is stale. A stub never proves that something is missing,
   optional, or non-optional.

When two levels disagree, the higher one wins. Say so in the answer.

## 2. Scripts

Run the first three with `$QGIS_PYTHON`, and again with `$QGIS4_PYTHON` when Qt 6 matters.

| Script | Use |
|---|---|
| `api_doc.py NAME` | signatures, doc, signal types, defining class, and the header / cpp / sip lines for NAME; `--members` lists a class |
| `check_ui.py FILE.ui ... \| DIR` | compile + headless load of `.ui` files with this Python's PyQt |
| `render_ui.py FILE.ui` | PNG of the dialog; then Read the PNG |
| `find_source.py RX` | `git grep` in the QGIS 3 / QGIS 4 / cookbook / Qt / PyQt sources (any Python) |
| `pyqgis_env.py` | path resolution (section 0) |

Direct checks are fine too:

```
"$QGIS_PYTHON" -c "from qgis.core import QgsVectorLayer; print(QgsVectorLayer.selectionChanged.signatures)"
"$QGIS_PYTHON" -c "from qgis.testing import start_app; start_app(); import my_plugin"   # headless import smoke test
"$QGIS_PYTHON" -m pytest tests -q
"$QGIS4_PYTHON" -m pytest tests -q
```

## 3. Rules for plugin code

- Import Qt only through `qgis.PyQt` (`from qgis.PyQt.QtWidgets import QAction`,
  `from qgis.PyQt import sip, uic`). A direct `PyQt5` or `PyQt6` import breaks on the
  other QGIS major.
- Write to the Qt 5 / Qt 6 intersection: scoped enums (`Qt.AlignmentFlag.AlignLeft`),
  `exec()`, `QRegularExpression`, `pyqtSignal(object)`. Rules and the rename table:
  `reference/qt5-qt6.md`.
- Null attribute values: `QgsVariantUtils.isNull(v)` or `v == NULL`. On Qt 5 the value is
  a `QVariant`, so `is None` is False there. Details: `reference/pyqt-pitfalls.md`, section 4.
- Ownership: read the annotation before you pass an object to C++. No annotation
  (for example `QgsMapCanvas.setMapTool`) means **you** keep it alive: store it on `self`.
  `SIP_TRANSFER` (for example `QgsProject.addMapLayer`, `QgsTaskManager.addTask`,
  `QgsMessageBar.pushWidget`) means C++ owns it from then on. Details: `reference/pyqt-pitfalls.md`.
- Signals: connect with the real signature (section 1). Exceptions inside slots abort the
  slot; wrap risky work and log with `QgsMessageLog`.
- Threads: `QgsTask.run()` runs off the main thread. No GUI, no layer edits there.
  Send results back with signals.
- Gate on features, not versions, when possible. Otherwise `Qgis.QGIS_VERSION_INT >= 34000`
  and `QT_VERSION_STR`.
- `.ui` files: check every edit with `check_ui.py` under each QGIS Python, then look at
  the `render_ui.py` picture. Custom widgets and hand-editing rules: `reference/ui-files.md`.
- A change is done when pytest passes under every QGIS Python you have. The headless
  setup (`start_app`, mock `iface`, a `conftest.py`): `reference/qt5-qt6.md`, Testing both.
- Migrating a QGIS 3 plugin to QGIS 4: the `qgis4-migration` skill in this collection
  (sibling folder `../qgis4-migration`).

## 4. Reference notes

- `reference/lookup.md`: where each fact lives in the clones, SIP annotation cheat sheet,
  grep recipes, URL patterns.
- `reference/pyqt-pitfalls.md`: ownership, lifetime, signals, threads, NULL / QVariant,
  symptom-to-cause table.
- `reference/qt5-qt6.md`: dual-compatibility rules, the rename table, testing under both.
- `reference/ui-files.md`: Qt Designer XML, custom widgets, loading, checking, rendering.
- Cookbook chapters in `$QGIS_DOCS_SRC/docs/pyqgis_developer_cookbook/`: `plugins/plugins.rst`
  (structure, `metadata.txt`, `classFactory`, `initGui`, `unload`), `plugins/releasing.rst`,
  `tasks.rst`, `vector.rst`, `canvas.rst`, `settings.rst`, `communicating.rst`, `cheat_sheet.rst`.
  Search them with `find_source.py "text" --docs`.
