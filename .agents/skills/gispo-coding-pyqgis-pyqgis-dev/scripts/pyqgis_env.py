#!/usr/bin/env python3
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Find the QGIS / Qt sources, the QGIS docs and the QGIS-capable Pythons on this machine.

Resolution order for every item: environment variable -> auto-detect -> missing.

    python pyqgis_env.py            # human report + a config block to paste
    python pyqgis_env.py --json     # machine readable
    python pyqgis_env.py --quick    # skip the (slow) Python probes

QGIS 3 always uses Qt 5 / PyQt5. QGIS 4 always uses Qt 6 / PyQt6.

Environment variables (all optional; auto-detect fills the gaps):
    QGIS_PYTHON         Python that can `import qgis.core`. Your main QGIS; QGIS 3 if you have both.
    QGIS4_PYTHON        A second Python with QGIS 4, for cross-checking (optional; most people have one venv)
    QGIS_SRC            QGIS 3.x source checkout      (contains src/core/qgis.h)
    QGIS4_SRC           QGIS 4.x source checkout
    QGIS_DOCS_SRC       QGIS-Documentation checkout   (contains docs/pyqgis_developer_cookbook)
    QTBASE_SRC          Qt 5 qtbase checkout          (contains src/corelib/kernel/qobject.h)
    QTBASE6_SRC         Qt 6 qtbase checkout
    PYQT_BINDINGS       PyQt5 sip binding files (.../PyQt5/bindings); found from the Qt 5 Python
    PYQT6_BINDINGS      PyQt6 sip binding files; found from the Qt 6 Python
    PYQGIS_SEARCH_PATH  extra directories to search, separated by os.pathsep

Auto-detect looks in: the current directory, its three parents, your home directory,
PYQGIS_SEARCH_PATH, and the children and grandchildren of all of those.
Relative paths are taken from the current directory.

Other scripts do `from pyqgis_env import resolve`.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KEYS = [
    "QGIS_PYTHON",
    "QGIS4_PYTHON",
    "QGIS_SRC",
    "QGIS4_SRC",
    "QGIS_DOCS_SRC",
    "QTBASE_SRC",
    "QTBASE6_SRC",
    "PYQT_BINDINGS",
    "PYQT6_BINDINGS",
]
_DIR_KEYS = ("QGIS_SRC", "QGIS4_SRC", "QGIS_DOCS_SRC", "QTBASE_SRC", "QTBASE6_SRC")
_PY_KEYS = ("QGIS_PYTHON", "QGIS4_PYTHON", "PYQT_BINDINGS", "PYQT6_BINDINGS")
_NAME_RE = re.compile(r"qgis|qt", re.IGNORECASE)
_MAX_CHILDREN = 400
_MAX_PROBES = 8
_WIN = sys.platform.startswith("win")

HINTS = {
    "QGIS_PYTHON": "a Python that imports qgis: python-qgis.bat or python-qgis-ltr.bat in the bin folder of a QGIS "
    "install or OSGeo4W on Windows, the system python3 with the QGIS packages on Linux, or a qgis/qgis Docker image",
    "QGIS4_PYTHON": "optional: a Python with QGIS 4 (QGIS 4 installer, or qgis-qt6-dev in OSGeo4W) "
    "to cross-check Qt 6 behaviour",
    "QGIS_SRC": "git clone --depth 1 --branch release-3_44 https://github.com/qgis/QGIS.git <dir>/QGIS",
    "QGIS4_SRC": "git clone --depth 1 --branch release-4_2 https://github.com/qgis/QGIS.git <dir>/QGIS-4_2",
    "QGIS_DOCS_SRC": "git clone --depth 1 https://github.com/qgis/QGIS-Documentation.git <dir>/QGIS-Documentation",
    "QTBASE_SRC": "git clone --depth 1 --branch 5.15 https://github.com/qt/qtbase.git <dir>/qtbase-5.15",
    "QTBASE6_SRC": "git clone --depth 1 --branch 6.11 https://github.com/qt/qtbase.git <dir>/qtbase-6.11",
    "PYQT_BINDINGS": "found automatically next to the PyQt5 package of a Qt 5 Python; on Linux the "
    "distro may ship it in a -dev package",
    "PYQT6_BINDINGS": "found automatically next to the PyQt6 package of a Qt 6 Python",
}

_PROBE = r"""
import json, sys
out = {"exe": sys.executable}
try:
    import qgis.core
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    out.update(qgis=Qgis.QGIS_VERSION, qt=QT_VERSION_STR, pyqt=PYQT_VERSION_STR)
    out["qgis_major"] = int(Qgis.QGIS_VERSION.split(".")[0])
    out["qt_major"] = int(QT_VERSION_STR.split(".")[0])
    import importlib, os
    pkg = importlib.import_module("PyQt6" if out["qt_major"] >= 6 else "PyQt5")
    b = os.path.join(os.path.dirname(pkg.__file__), "bindings")
    out["bindings"] = b if os.path.isdir(b) else None
except Exception as e:  # noqa: BLE001
    out["error"] = repr(e)
print("PYQGIS_PROBE=" + json.dumps(out))
"""


# --------------------------------------------------------------------------- directories
def _children(d: Path) -> list[Path]:
    out: list[Path] = []
    try:
        with os.scandir(d) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False) and not e.name.startswith("."):
                        out.append(Path(e.path))
                except OSError:
                    continue
                if len(out) >= _MAX_CHILDREN:
                    break
    except OSError:
        pass
    return out


def _bases() -> list[Path]:
    cwd = Path.cwd().resolve()
    bases = [cwd, *cwd.parents[:3], Path.home()]
    for extra in os.environ.get("PYQGIS_SEARCH_PATH", "").split(os.pathsep):
        if extra.strip():
            bases.append(Path(extra.strip()).expanduser())
    seen: set[Path] = set()
    out: list[Path] = []
    for b in bases:
        if b.is_dir() and b not in seen:
            seen.add(b)
            out.append(b)
    return out


def _search(pred) -> Path | None:
    roots = _bases()
    seen: set[Path] = set(roots)
    level1: list[Path] = []
    for r in roots:
        for c in _children(r):
            if c not in seen:
                seen.add(c)
                level1.append(c)
    for d in roots:
        if pred(d):
            return d
    for d in level1:
        if _NAME_RE.search(d.name) and pred(d):
            return d
    for d in level1:
        for c in _children(d):
            if _NAME_RE.search(c.name) and pred(c):
                return c
    return None


def _is_qgis_src(p: Path) -> bool:
    return (p / "src" / "core" / "qgis.h").is_file()


def _qgis_version(p: Path) -> str | None:
    f = p / "CMakeLists.txt"
    try:
        txt = f.read_text(errors="ignore")
    except OSError:
        return None
    major = re.search(r'CPACK_PACKAGE_VERSION_MAJOR\s+"(\d+)"', txt)
    minor = re.search(r'CPACK_PACKAGE_VERSION_MINOR\s+"(\d+)"', txt)
    if not major:
        return None
    return major.group(1) + ("." + minor.group(1) if minor else "")


def _qgis_major(p: Path) -> int | None:
    v = _qgis_version(p)
    return int(v.split(".")[0]) if v else None


def _is_docs(p: Path) -> bool:
    return (p / "docs" / "pyqgis_developer_cookbook" / "index.rst").is_file()


def _is_qtbase(p: Path) -> bool:
    return (p / "src" / "corelib" / "kernel" / "qobject.h").is_file()


def _qt_version(p: Path) -> str | None:
    for name, rx in (
        (".cmake.conf", r'QT_REPO_MODULE_VERSION\s+"([\d.]+)'),
        (".qmake.conf", r"MODULE_VERSION\s*=\s*([\d.]+)"),
    ):
        f = p / name
        if f.is_file():
            m = re.search(rx, f.read_text(errors="ignore"))
            if m:
                return m.group(1)
    return None


def _qt_major(p: Path) -> int | None:
    v = _qt_version(p)
    return int(v.split(".")[0]) if v else None


def _git_ref(p: Path) -> str:
    head = p / ".git" / "HEAD"
    try:
        txt = head.read_text().strip()
    except OSError:
        return "not a git checkout"
    if txt.startswith("ref: refs/heads/"):
        return "branch " + txt[len("ref: refs/heads/") :]
    return "commit " + txt[:10]


_DIR_SPECS = {
    "QGIS_SRC": (
        lambda p: _is_qgis_src(p) and (_qgis_major(p) or 3) < 4,
        lambda p: f"QGIS {_qgis_version(p)}, {_git_ref(p)}",
    ),
    "QGIS4_SRC": (
        lambda p: _is_qgis_src(p) and (_qgis_major(p) or 0) >= 4,
        lambda p: f"QGIS {_qgis_version(p)}, {_git_ref(p)}",
    ),
    "QGIS_DOCS_SRC": (_is_docs, lambda p: _git_ref(p)),
    "QTBASE_SRC": (
        lambda p: _is_qtbase(p) and _qt_major(p) == 5,
        lambda p: f"Qt {_qt_version(p)}, {_git_ref(p)}",
    ),
    "QTBASE6_SRC": (
        lambda p: _is_qtbase(p) and _qt_major(p) == 6,
        lambda p: f"Qt {_qt_version(p)}, {_git_ref(p)}",
    ),
}


# --------------------------------------------------------------------------- pythons
def _probe_python(exe: str) -> dict:
    fd, path = tempfile.mkstemp(suffix=".py", prefix="pyqgis_probe_")
    with os.fdopen(fd, "w") as f:
        f.write(_PROBE)
    try:
        r = subprocess.run([exe, path], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": repr(e)}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    for line in reversed((r.stdout or "").splitlines()):
        if line.startswith("PYQGIS_PROBE="):
            try:
                return json.loads(line[len("PYQGIS_PROBE=") :])
            except json.JSONDecodeError:
                break
    return {"error": (r.stderr or r.stdout or "no output").strip()[-300:]}


def _python_candidates() -> list[tuple[str, str]]:
    """(path, source) in priority order."""
    cands: list[tuple[str, str]] = []
    for k in ("QGIS_PYTHON", "QGIS4_PYTHON"):
        v = os.environ.get(k)
        if v:
            cands.append((os.path.abspath(os.path.expanduser(v)), "env"))
    cwd = Path.cwd()
    for venv in sorted(cwd.glob(".venv*")):
        for rel in ("Scripts/python.exe", "bin/python"):
            if (venv / rel).is_file():
                cands.append((str(venv / rel), "auto"))
    if _WIN:
        for pat in (
            r"C:\OSGeo4W*\bin\python-qgis*.bat",
            r"C:\Program Files\QGIS*\bin\python-qgis*.bat",
        ):
            cands.extend((p, "auto") for p in sorted(glob.glob(pat), reverse=True))
    else:
        for name in ("python3", "python"):
            w = shutil.which(name)
            if w:
                cands.append((w, "auto"))
    cands.append((sys.executable, "auto"))
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for p, src in cands:
        key = os.path.normcase(os.path.normpath(p))
        if key not in seen and (os.path.isfile(p) or shutil.which(p)):
            seen.add(key)
            out.append((p, src))
    return out


def _find_pythons(quick: bool) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if quick:
        for k in _PY_KEYS:
            v = os.environ.get(k)
            out[k] = {
                "value": v or None,
                "source": "env" if v else "missing",
                "detail": "not probed (--quick)" if v else "",
            }
        return out
    q3 = q4 = None
    probes = 0
    warnings: list[str] = []
    for exe, src in _python_candidates():
        if probes >= _MAX_PROBES or (q3 and q4):
            break
        probes += 1
        info = _probe_python(exe)
        if "error" in info:
            if src == "env":
                warnings.append(f"{exe}: {info['error']}")
            continue
        entry = {"exe": exe, "source": src, "info": info}
        if info.get("qgis_major", 3) >= 4:
            q4 = q4 or entry
        else:
            q3 = q3 or entry
    primary = q3 or q4
    second = q4 if (q4 is not None and q4 is not primary) else None

    def describe(entry: dict) -> str:
        i = entry["info"]
        return f"QGIS {i['qgis']} | Qt {i['qt']} | PyQt {i['pyqt']}"

    out["QGIS_PYTHON"] = (
        {
            "value": primary["exe"],
            "source": primary["source"],
            "detail": describe(primary),
        }
        if primary
        else {"value": None, "source": "missing", "detail": ""}
    )
    out["QGIS4_PYTHON"] = (
        {"value": second["exe"], "source": second["source"], "detail": describe(second)}
        if second
        else {
            "value": None,
            "source": "missing",
            "detail": "QGIS_PYTHON is already QGIS 4"
            if (primary and primary is q4)
            else "",
        }
    )
    for key, qt_major in (("PYQT_BINDINGS", 5), ("PYQT6_BINDINGS", 6)):
        env_b = os.environ.get(key)
        found = next(
            (
                e["info"]["bindings"]
                for e in (primary, second)
                if e
                and e["info"].get("qt_major") == qt_major
                and e["info"].get("bindings")
            ),
            None,
        )
        out[key] = {
            "value": env_b or found,
            "source": "env" if env_b else ("auto" if found else "missing"),
            "detail": "",
        }
    if warnings:
        out["_warnings"] = {"value": None, "source": "", "detail": "\n".join(warnings)}
    return out


# --------------------------------------------------------------------------- public
def resolve(keys=None, quick: bool = False) -> dict[str, dict]:
    """Return {KEY: {"value": str|None, "source": "env"|"auto"|"missing", "detail": str}}."""
    keys = list(keys or KEYS)
    out: dict[str, dict] = {}
    for k in _DIR_KEYS:
        if k not in keys:
            continue
        pred, describe = _DIR_SPECS[k]
        env = os.environ.get(k)
        if env:
            p = Path(env).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            ok = p.is_dir() and pred(p)
            out[k] = {
                "value": str(p),
                "source": "env",
                "detail": describe(p)
                if ok
                else "WARNING: does not look like the expected checkout",
            }
        else:
            found = _search(pred)
            out[k] = {
                "value": str(found) if found else None,
                "source": "auto" if found else "missing",
                "detail": describe(found) if found else "",
            }
    if any(k in keys for k in _PY_KEYS):
        out.update(_find_pythons(quick))
    return out


def _settings_block(res: dict[str, dict]) -> str:
    env = {k: res[k]["value"] for k in KEYS if res.get(k, {}).get("value")}
    return json.dumps({"env": env}, indent=2)


def _report(res: dict[str, dict]) -> str:
    lines = ["PyQGIS development environment", ""]
    for k in KEYS:
        r = res.get(k, {"value": None, "source": "missing", "detail": ""})
        val = r["value"] or "-"
        lines.append(f"  {k:<16} {r['source']:<8} {val}")
        if r["detail"]:
            lines.append(f"  {'':<16} {'':<8}   {r['detail']}")
    warn = res.get("_warnings", {}).get("detail", "")
    if warn:
        lines += ["", "Problems with configured Pythons:"] + [
            "  " + w for w in warn.splitlines()
        ]
    missing = [k for k in KEYS if not res.get(k, {}).get("value")]
    if missing:
        lines += ["", "Missing (all optional except QGIS_PYTHON):"]
        for k in missing:
            lines.append(f"  {k}: {HINTS[k]}")
    lines += [
        "",
        "To skip auto-detect next time, paste this into .claude/settings.local.json",
        "(Claude Code; the file is personal and not committed), or export the same",
        "names in your shell:",
        _settings_block(res),
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    quick = "--quick" in argv
    res = resolve(quick=quick)
    if "--json" in argv:
        print(
            json.dumps(
                {k: v for k, v in res.items() if not k.startswith("_")}, indent=2
            )
        )
    else:
        print(_report(res))
    return 0 if res.get("QGIS_PYTHON", {}).get("value") or quick else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
