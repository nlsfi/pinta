# One code base for Qt 5 (QGIS 3.x) and Qt 6 (QGIS 4.x)

QGIS 3.x ships PyQt5. QGIS 4.x ships PyQt6. The `qgis.PyQt` package maps to whichever is
present and adds a few compatibility re-exports. Write to the intersection.

## Rules

1. Import Qt only through `qgis.PyQt`: `from qgis.PyQt.QtCore import Qt`. Never `PyQt5` or `PyQt6`. Also `from qgis.PyQt import sip, uic`.
2. `QAction`, `QActionGroup`, `QShortcut` moved from QtWidgets to QtGui in Qt 6. Through `qgis.PyQt` both `from qgis.PyQt.QtWidgets import QAction` and `from qgis.PyQt.QtGui import QAction` work on QGIS 3.44 and 4.2 (checked live; the shim re-exports in both directions). Pick one and stay consistent.
3. Enums: always the scoped form. `Qt.AlignmentFlag.AlignLeft`, `Qt.ItemDataRole.UserRole`, `QMessageBox.StandardButton.Yes`. PyQt6 has no unscoped names. PyQt5 accepts both.
4. `int(enum_member)` works on both (checked with PyQt 6.11 for `Qt.CheckState`, `Qt.AlignmentFlag` and `Qgis.LayerType`). `.value` and `.name` exist only on PyQt6. Combine flags with `|` on both. Prefer storing the member, not an int.
5. `exec()`, not `exec_()`. Both PyQts have `exec()`.
6. `QRegularExpression`, never `QRegExp`.
7. `pyqtSignal(object)` for values that are `QVariant` in C++. `QMetaType.Type.Int` instead of `QVariant.Type`; null tests and the details of both: `pyqt-pitfalls.md` section 4.
8. `QFontMetrics.horizontalAdvance()`, not `width()` (exists since Qt 5.11).
9. `Qt.MouseButton.MiddleButton`, not `MidButton`.
10. `QApplication.primaryScreen()` instead of `QDesktopWidget`.
11. `QComboBox.currentTextChanged` instead of `currentIndexChanged[str]`.
12. Web views have no shared module: QGIS 3 ships `QtWebKitWidgets` and no `QtWebEngineWidgets`, QGIS 4 the reverse (checked on OSGeo4W 3.44 and 4.0). Gate the import with `try` / `except ImportError` and offer a fallback (`QTextBrowser`, or `QDesktopServices.openUrl`).
13. QGIS enums: prefer the scoped `Qgis.*` forms (`Qgis.LayerType.Vector`, `Qgis.WkbType.Point`, `Qgis.GeometryType.Polygon`, `Qgis.DistanceUnit.Meters`) when the minimum QGIS version has them; most arrived in 3.30 to 3.36 (check `\since` in `src/core/qgis.h`). The migration script writes the class-scoped aliases instead (`QgsMapLayer.LayerType.VectorLayer`, `QgsWkbTypes.GeometryType.PolygonGeometry`); those work on 3.44 and 4.2 too (checked live). Whether an old spelling survives in QGIS 4 is a live check: `api_doc.py` under `$QGIS4_PYTHON`.
14. Gate on features when you must diverge:

```python
from qgis.core import Qgis
from qgis.PyQt.QtCore import QT_VERSION_STR

QT6 = QT_VERSION_STR.startswith("6")
if Qgis.QGIS_VERSION_INT >= 34000:
    ...
```

## Rename table (left breaks on Qt 6; right works on both)

| Qt 5 only | Both |
|---|---|
| `Qt.AlignLeft` | `Qt.AlignmentFlag.AlignLeft` |
| `Qt.UserRole` | `Qt.ItemDataRole.UserRole` |
| `Qt.Checked` | `Qt.CheckState.Checked` |
| `Qt.Horizontal` | `Qt.Orientation.Horizontal` |
| `Qt.ItemIsEnabled` | `Qt.ItemFlag.ItemIsEnabled` |
| `Qt.KeepAspectRatio` | `Qt.AspectRatioMode.KeepAspectRatio` |
| `Qt.WaitCursor` | `Qt.CursorShape.WaitCursor` |
| `Qt.Key_Escape` | `Qt.Key.Key_Escape` |
| `Qt.LeftButton` | `Qt.MouseButton.LeftButton` |
| `Qt.Dialog` (window flag) | `Qt.WindowType.Dialog` |
| `QMessageBox.Yes` | `QMessageBox.StandardButton.Yes` |
| `QMessageBox.Warning` | `QMessageBox.Icon.Warning` |
| `QDialogButtonBox.Ok` | `QDialogButtonBox.StandardButton.Ok` |
| `QAbstractItemView.SingleSelection` | `QAbstractItemView.SelectionMode.SingleSelection` |
| `QAbstractItemView.SelectRows` | `QAbstractItemView.SelectionBehavior.SelectRows` |
| `QHeaderView.Stretch` | `QHeaderView.ResizeMode.Stretch` |
| `QSizePolicy.Expanding` | `QSizePolicy.Policy.Expanding` |
| `QFrame.StyledPanel` | `QFrame.Shape.StyledPanel` |
| `QLineEdit.Password` | `QLineEdit.EchoMode.Password` |
| `QFileDialog.ShowDirsOnly` | `QFileDialog.Option.ShowDirsOnly` |
| `QStyle.SP_DialogOkButton` | `QStyle.StandardPixmap.SP_DialogOkButton` |
| `QPalette.Window` | `QPalette.ColorRole.Window` |
| `QDialog.Accepted` | `QDialog.DialogCode.Accepted` |
| `dialog.exec_()` | `dialog.exec()` |
| `QRegExp` | `QRegularExpression` |
| `QVariant.Type.Int` (`QVariant.Int` still works on 4.2) | `QMetaType.Type.Int` |
| `QFontMetrics.width(s)` | `QFontMetrics.horizontalAdvance(s)` |
| `QDesktopWidget().screenGeometry()` | `QApplication.primaryScreen().geometry()` |
| `combo.currentIndexChanged[str]` | `combo.currentTextChanged` |
| `pyqtSignal(QVariant)` | `pyqtSignal(object)` |
| `from qgis.PyQt.QtWebKitWidgets import QWebView` | gated import of `QtWebEngineWidgets` with a fallback (rule 12) |
| `QgsMapLayer.VectorLayer` (still accepted on 4.2) | `Qgis.LayerType.Vector` or `QgsMapLayer.LayerType.VectorLayer` |
| `QgsWkbTypes.Point` | `Qgis.WkbType.Point` |
| `QgsWkbTypes.PolygonGeometry` (still accepted on 4.2) | `Qgis.GeometryType.Polygon` or `QgsWkbTypes.GeometryType.PolygonGeometry` |
| `QgsUnitTypes.DistanceMeters` | `Qgis.DistanceUnit.Meters` |

Find the scoped name when unsure:
`"$QGIS_PYTHON" api_doc.py Qt --members --grep Align` or
`"$QGIS_PYTHON" api_doc.py QMessageBox --members --grep StandardButton`.

## .ui files

Both uic versions read the file when it keeps Qt 5 enum spelling and every custom widget
accepts `parent` as its first parameter. Rules, checks and rendering: `ui-files.md`.

## Migrating an existing QGIS 3 plugin

Use the `qgis4-migration` skill from the same collection (sibling folder `../../qgis4-migration`):
the `pyqt5_to_pyqt6.py` script, an inventory scan, what the script cannot fix, `metadata.txt`, testing.

## Testing both

Use pytest and run the suite under each QGIS Python:

```
"$QGIS_PYTHON"  -m pytest tests -q
"$QGIS4_PYTHON" -m pytest tests -q
```

The headless setup comes from QGIS itself; no extra pytest plugin package is needed.
A minimal `tests/conftest.py`:

```python
import pytest
from qgis.testing import start_app
from qgis.testing.mocked import get_iface


@pytest.fixture(scope="session", autouse=True)
def qgis_app():
    yield start_app()          # QgsApplication without a display; cleaned up at exit


@pytest.fixture
def iface():
    return get_iface()         # mock QgisInterface with a real map canvas
```

`qgis.testing.QgisTestCase` extends `unittest.TestCase` with QGIS asserts (layers, geometries,
rendered images) and works under pytest too.

Where each Python comes from: `python-qgis.bat` or `python-qgis-ltr.bat` in the `bin` folder
of a QGIS install or of OSGeo4W (Windows), the system `python3` with the QGIS packages (Linux),
or the `qgis/qgis` Docker images (`release-3_44`, `latest`).
