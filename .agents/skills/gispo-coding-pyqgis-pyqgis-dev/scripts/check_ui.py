#!/usr/bin/env python3
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Check that Qt Designer .ui files compile and load with the PyQt of *this* Python.

    "$QGIS_PYTHON"     check_ui.py path/to/file.ui other.ui     # Qt 5 side
    "$QGIS4_PYTHON" check_ui.py plugin_dir/                  # Qt 6 side; a directory means **/*.ui

Two checks per file:
  compile  uic turns the XML into Python  (unknown widgets, bad properties, enum spellings)
  load     uic.loadUi builds the real widgets headless  (custom-widget imports, runtime errors)
Custom widgets with a dotted <header> are imported from the current directory; add --path DIR for more.
Exit code 1 when any file fails. Run it under both Pythons before you call a .ui change done.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("targets", nargs="+", help=".ui files or directories")
    ap.add_argument(
        "--path",
        action="append",
        default=[],
        help="extra sys.path entry for custom widgets (repeatable)",
    )
    ap.add_argument(
        "--no-load", action="store_true", help="only compile, do not build widgets"
    )
    a = ap.parse_args()

    files: list[Path] = []
    for t in a.targets:
        p = Path(t)
        files += sorted(p.rglob("*.ui")) if p.is_dir() else [p]
    if not files:
        sys.exit("no .ui files found")

    sys.path.insert(0, os.getcwd())
    for extra in a.path:
        sys.path.insert(0, os.path.abspath(extra))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.PyQt import uic
    from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QObject

    print(f"Qt {QT_VERSION_STR} | PyQt {PYQT_VERSION_STR}")
    app = None
    if not a.no_load:
        from qgis.core import QgsApplication

        app = QgsApplication([], False)
        app.initQgis()

    failed = 0
    for f in files:
        status = []
        try:
            uic.compileUi(str(f), io.StringIO())
            status.append("compile ok")
        except Exception as e:  # noqa: BLE001
            status.append(f"COMPILE FAIL: {type(e).__name__}: {e}")
            failed += 1
            print(f"{f}: " + "; ".join(status))
            continue
        if app is not None:
            try:
                w = uic.loadUi(str(f))
                status.append(
                    f"load ok ({type(w).__name__}, {len(w.findChildren(QObject))} children)"
                )
                w.deleteLater()
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc().strip().splitlines()[-1]
                status.append(f"LOAD FAIL: {tb}")
                failed += 1
        print(f"{f}: " + "; ".join(status))

    if app is not None:
        app.processEvents()
        app.exitQgis()
    print(f"{len(files) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
