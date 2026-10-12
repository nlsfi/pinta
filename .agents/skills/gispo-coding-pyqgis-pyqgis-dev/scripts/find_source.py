#!/usr/bin/env python3
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Search a source checkout. Fast: runs `git grep` inside the clone. Any Python works.

    python find_source.py "setMapTool"                       # QGIS 3: sip files + src/core, src/gui, src/analysis
    python find_source.py "setMapTool" --qgis4               # the same in the QGIS 4 checkout
    python find_source.py "SIP_TRANSFER" --h --path src/gui  # ownership annotations in headers
    python find_source.py "class CORE_EXPORT QgsTask" --h
    python find_source.py "QgsTask::run" --cpp -C 3
    python find_source.py "setModel" --sip                   # only the .sip.in binding files
    python find_source.py "QAbstractItemView::setModel" --qt --cpp
    python find_source.py "horizontalAdvance" --qt6 --h
    python find_source.py "KeepReference" --pyqt              # PyQt5 sip binding files
    python find_source.py "QgsTask" --docs                    # PyQGIS developer cookbook (.rst)
    python find_source.py "QgsVectorLayer(" --py --path python/plugins --path tests/src/python   # usage examples

PATTERN is an extended regex (git grep -E). --fixed makes it literal, -i ignores case.
Roots come from QGIS_SRC / QGIS4_SRC / QGIS_DOCS_SRC / QTBASE_SRC / QTBASE6_SRC /
PYQT_BINDINGS / PYQT6_BINDINGS (see pyqgis_env.py).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

QGIS3_DIRS = [
    "python/core",
    "python/gui",
    "python/analysis",
    "src/core",
    "src/gui",
    "src/analysis",
]
QGIS4_DIRS = [
    "python/PyQt6/core",
    "python/PyQt6/gui",
    "python/PyQt6/analysis",
    "src/core",
    "src/gui",
    "src/analysis",
]
QT_DIRS = [
    "src/corelib",
    "src/gui",
    "src/widgets",
    "src/network",
    "src/xml",
    "src/sql",
    "src/printsupport",
    "src/testlib",
]
DOCS_DIRS = ["docs/pyqgis_developer_cookbook"]


def _root(key: str) -> Path:
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import pyqgis_env

    quick = key not in (
        "PYQT_BINDINGS",
        "PYQT6_BINDINGS",
    )  # bindings need the Python probe
    r = pyqgis_env.resolve([key], quick=quick)[key]
    if not r["value"]:
        sys.exit(
            f"{key} is not set and was not found. Run pyqgis_env.py; hint: {pyqgis_env.HINTS[key]}"
        )
    return Path(r["value"])


def _pathspecs(dirs: list[str], exts: list[str]) -> list[str]:
    if not exts:
        return dirs
    return [f":(glob){d}/**/*{e}" for d in dirs for e in exts]


def _git_grep(
    root: Path, pattern: str, specs: list[str], fixed: bool, icase: bool, context: int
) -> tuple[list[str], bool]:
    cmd = ["git", "-C", str(root), "grep", "-n", "-I", "-F" if fixed else "-E"]
    if icase:
        cmd.append("-i")
    if context:
        cmd += ["-C", str(context)]
    cmd += ["-e", pattern, "--", *specs]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except OSError:
        return [], False
    if r.returncode not in (0, 1):
        return [], False
    return r.stdout.splitlines(), True


def _py_grep(
    root: Path, pattern: str, dirs: list[str], exts: list[str], fixed: bool, icase: bool
) -> list[str]:
    """Slow fallback when the root is not a git checkout."""
    rx = re.compile(
        re.escape(pattern) if fixed else pattern, re.IGNORECASE if icase else 0
    )
    out: list[str] = []
    for d in dirs:
        for dirpath, _, files in os.walk(root / d):
            for fn in files:
                if exts and not any(fn.endswith(e) for e in exts):
                    continue
                p = Path(dirpath) / fn
                try:
                    for i, line in enumerate(
                        p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        if rx.search(line):
                            out.append(f"{p.relative_to(root).as_posix()}:{i}:{line}")
                except OSError:
                    continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("pattern")
    where = ap.add_mutually_exclusive_group()
    where.add_argument(
        "--qgis4",
        action="store_true",
        help="search the QGIS 4 checkout (QGIS4_SRC) instead of QGIS 3",
    )
    where.add_argument(
        "--docs",
        action="store_true",
        help="search the PyQGIS developer cookbook (QGIS_DOCS_SRC)",
    )
    where.add_argument(
        "--qt", action="store_true", help="search the Qt 5 checkout (QTBASE_SRC)"
    )
    where.add_argument(
        "--qt6", action="store_true", help="search the Qt 6 checkout (QTBASE6_SRC)"
    )
    where.add_argument(
        "--pyqt",
        action="store_true",
        help="search the PyQt5 sip bindings (PYQT_BINDINGS)",
    )
    where.add_argument(
        "--pyqt6",
        action="store_true",
        help="search the PyQt6 sip bindings (PYQT6_BINDINGS)",
    )
    ap.add_argument("--sip", action="store_true", help="only *.sip.in / *.sip files")
    ap.add_argument("--h", action="store_true", help="only *.h files")
    ap.add_argument("--cpp", action="store_true", help="only *.cpp files")
    ap.add_argument(
        "--py",
        action="store_true",
        help="only *.py files (QGIS bundled plugins, tests)",
    )
    ap.add_argument(
        "--path",
        action="append",
        default=[],
        metavar="DIR",
        help="search these dirs instead of the defaults (repeatable)",
    )
    ap.add_argument("-C", "--context", type=int, default=0, help="lines of context")
    ap.add_argument("--max", type=int, default=80, help="max output lines (default 80)")
    ap.add_argument(
        "--fixed", action="store_true", help="literal string instead of regex"
    )
    ap.add_argument("-i", action="store_true", help="ignore case")
    a = ap.parse_args()

    if a.qt or a.qt6:
        root, dirs = _root("QTBASE6_SRC" if a.qt6 else "QTBASE_SRC"), QT_DIRS
    elif a.pyqt or a.pyqt6:
        root, dirs = _root("PYQT6_BINDINGS" if a.pyqt6 else "PYQT_BINDINGS"), ["."]
    elif a.docs:
        root, dirs = _root("QGIS_DOCS_SRC"), DOCS_DIRS
    elif a.qgis4:
        root, dirs = _root("QGIS4_SRC"), QGIS4_DIRS
    else:
        root, dirs = _root("QGIS_SRC"), QGIS3_DIRS
    if a.path:
        dirs = a.path
    exts: list[str] = []
    if a.sip:
        exts += [".sip.in", ".sip"]
    if a.h:
        exts.append(".h")
    if a.cpp:
        exts.append(".cpp")
    if a.py:
        exts.append(".py")

    print(f"root: {root}")
    lines, ok = _git_grep(
        root, a.pattern, _pathspecs(dirs, exts), a.fixed, a.i, a.context
    )
    if not ok:
        print("(git grep unavailable here; slow Python scan)")
        lines = _py_grep(root, a.pattern, dirs, exts, a.fixed, a.i)
    if not lines:
        print("no matches")
        return 1
    for line in lines[: a.max]:
        print(line[:220])
    if len(lines) > a.max:
        print(
            f"... {len(lines) - a.max} more lines. Raise --max or narrow with --path / --h / --cpp / --sip / --py."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
