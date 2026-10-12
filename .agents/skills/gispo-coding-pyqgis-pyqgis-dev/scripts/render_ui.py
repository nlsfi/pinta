#!/usr/bin/env python3
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Render a Qt Designer .ui file to a PNG without a display. Then look at the PNG.

    "$QGIS_PYTHON" render_ui.py path/to/dialog.ui                    # -> <tmp>/dialog.png
    "$QGIS_PYTHON" render_ui.py dialog.ui -o out.png --width 900 --height 600
    "$QGIS_PYTHON" render_ui.py dialog.ui --names                    # empty labels/buttons show their objectName
    "$QGIS4_PYTHON" render_ui.py dialog.ui                        # same picture under Qt 6

QGIS widgets (QgsFilterLineEdit, QgsFileWidget, ...) render because a QgsApplication is started.
Plugin-own custom widgets are imported from the current directory (add --path DIR for more).
Text that the plugin sets at run time is empty in the picture; --names shows which widget is where.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("ui_file")
    ap.add_argument("-o", "--out", help="PNG path (default: <temp dir>/<ui name>.png)")
    ap.add_argument("--width", type=int, help="force width in px")
    ap.add_argument("--height", type=int, help="force height in px")
    ap.add_argument(
        "--names",
        action="store_true",
        help="put objectName into empty labels, buttons and group boxes",
    )
    ap.add_argument(
        "--path",
        action="append",
        default=[],
        help="extra sys.path entry for custom widgets (repeatable)",
    )
    a = ap.parse_args()

    ui = Path(a.ui_file)
    if not ui.is_file():
        sys.exit(f"not a file: {ui}")
    out = Path(a.out) if a.out else Path(tempfile.gettempdir()) / (ui.stem + ".png")

    sys.path.insert(0, os.getcwd())
    for extra in a.path:
        sys.path.insert(0, os.path.abspath(extra))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import QgsApplication
    from qgis.PyQt import uic
    from qgis.PyQt.QtWidgets import QAbstractButton, QGroupBox, QLabel

    app = QgsApplication([], False)
    app.initQgis()
    w = uic.loadUi(str(ui))
    if a.names:
        for cls in (QLabel, QAbstractButton, QGroupBox):
            for child in w.findChildren(cls):
                if (
                    hasattr(child, "text")
                    and not child.text()
                    and hasattr(child, "setText")
                ):
                    child.setText(child.objectName())
                elif isinstance(child, QGroupBox) and not child.title():
                    child.setTitle(child.objectName())
    w.setWindowTitle(ui.name)
    if a.width or a.height:
        w.resize(a.width or w.sizeHint().width(), a.height or w.sizeHint().height())
    else:
        w.adjustSize()
        w.resize(max(w.width(), 400), max(w.height(), 150))
    w.show()
    app.processEvents()
    ok = w.grab().save(str(out))
    print(
        ("saved " if ok else "FAILED to save ") + f"{out}  ({w.width()}x{w.height()})"
    )
    w.close()
    app.exitQgis()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
