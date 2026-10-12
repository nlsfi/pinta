#!/usr/bin/env python3
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Ask the *live* QGIS Python what an API name really is. This beats stubs, docs and memory.

    "$QGIS_PYTHON" api_doc.py QgsVectorLayer.featureAdded     # signal: the real C++ signature
    "$QGIS_PYTHON" api_doc.py QgsVectorLayer.getFeatures       # method: signature(s), doc, source lines
    "$QGIS_PYTHON" api_doc.py QgsVectorLayer --members         # everything the class really has
    "$QGIS_PYTHON" api_doc.py QgsVectorLayer --members --grep select --inherited
    "$QGIS_PYTHON" api_doc.py QWidget.resize                   # Qt classes work the same way
    "$QGIS_PYTHON" api_doc.py Qgis.LayerType                   # enums list their members
    "$QGIS_PYTHON" api_doc.py qgis.utils.iface                 # any dotted path

Bare names are searched in qgis.core, qgis.gui, qgis.analysis and the qgis.PyQt modules.
Run it with $QGIS4_PYTHON as well when a QGIS 3 / QGIS 4 (Qt 5 / Qt 6) difference matters.
Source lines come from the checkout that matches this Python: QGIS_SRC or QGIS4_SRC, and
QTBASE_SRC or QTBASE6_SRC (see pyqgis_env.py). --no-source skips that.
"""

from __future__ import annotations

import argparse
import difflib
import enum
import importlib
import inspect
import re
import subprocess
import sys
from pathlib import Path

MODULES = [
    "qgis.core",
    "qgis.gui",
    "qgis.analysis",
    "qgis.PyQt.QtCore",
    "qgis.PyQt.QtGui",
    "qgis.PyQt.QtWidgets",
    "qgis.PyQt.QtNetwork",
    "qgis.PyQt.QtXml",
    "qgis.PyQt.QtSql",
    "qgis.PyQt.QtSvg",
    "qgis.PyQt.QtPrintSupport",
    "qgis.PyQt.QtTest",
    "qgis.PyQt.sip",
    "qgis.utils",
    "qgis.processing",
]
SIGNAL_TYPES = {"pyqtSignal", "pyqtBoundSignal"}
# sip method descriptors are not callable() themselves; recognise them by type name
_METHOD_TYPES = {
    "methoddescriptor",
    "method_descriptor",
    "builtin_function_or_method",
    "wrapper_descriptor",
    "function",
    "staticmethod",
    "classmethod",
}

# C++ -> Python hints for signal parameters (what the slot actually receives)
_CPP_PY = {
    "QgsFeatureId": "int",
    "qint64": "int",
    "qlonglong": "int",
    "int": "int",
    "uint": "int",
    "long": "int",
    "double": "float",
    "float": "float",
    "bool": "bool",
    "QString": "str",
    "QStringList": "list[str]",
    "QVariant": "Any (NULL is QVariant() on Qt 5, None on Qt 6)",
    "QgsFeatureIds": "set[int]",
    "QgsAttributes": "list",
    "QVariantMap": "dict",
    "QVariantList": "list",
    "QByteArray": "QByteArray",
}


def _versions() -> str:
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    return f"QGIS {Qgis.QGIS_VERSION} | Qt {QT_VERSION_STR} | PyQt {PYQT_VERSION_STR}"


def _import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001  (missing Qt module, import side effects, ...)
        return None


def _walk(mod, modname: str, attrs: list[str]):
    obj, owner = mod, None
    for a in attrs:
        try:
            owner, obj = obj, getattr(obj, a)
        except AttributeError:
            names = [n for n in dir(obj) if not n.startswith("_")]
            close = difflib.get_close_matches(a, names, n=8, cutoff=0.5)
            what = getattr(obj, "__name__", repr(obj))
            msg = f"{what} has no attribute '{a}' in this build ({_versions()})."
            if close:
                msg += "\nClose matches: " + ", ".join(close)
            msg += "\nIf a stub or doc says it exists, the stub/doc is wrong for this version, or it is SIP_SKIP'ped."
            sys.exit(msg)
    return modname, obj, owner


def resolve_name(name: str):
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        mod = _import(".".join(parts[:i]))
        if mod is not None:
            return _walk(mod, ".".join(parts[:i]), parts[i:])
    for modname in MODULES:
        mod = _import(modname)
        if mod is not None and hasattr(mod, parts[0]):
            return _walk(mod, modname, parts)
    sys.exit(
        f"'{name}' not found in {', '.join(MODULES)}.\nGive a dotted module path, e.g. qgis.core.{name}"
    )


def _is_enum(obj) -> bool:
    if not inspect.isclass(obj):
        return False
    if issubclass(obj, enum.Enum):
        return True
    return type(obj).__name__ == "enumtype"  # PyQt5 sip enums


def kind_of(obj) -> str:
    t = type(obj).__name__
    if t in SIGNAL_TYPES:
        return "signal"
    if inspect.ismodule(obj):
        return "module"
    if _is_enum(obj):
        return "enum"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "method/function"
    return "attribute"


def split_doc(doc: str | None) -> tuple[list[str], str]:
    """SIP docstrings start with one signature per line, then a blank line, then the text."""
    lines = (doc or "").strip("\n").splitlines()
    sigs: list[str] = []
    i = 0
    while (
        i < len(lines)
        and lines[i].strip()
        and "(" in lines[i]
        and not lines[i].startswith(" ")
    ):
        sigs.append(lines[i].strip())
        i += 1
    return sigs, "\n".join(lines[i:]).strip()


def defining_class(owner, attr: str):
    if not inspect.isclass(owner):
        return None
    for c in owner.__mro__:
        if attr in getattr(c, "__dict__", {}):
            return c
    return None


def enum_members(cls) -> list[tuple[str, object]]:
    if issubclass(cls, enum.Enum):
        return [(m.name, m.value) for m in cls]
    items = [(n, v) for n, v in vars(cls).items() if isinstance(v, cls)]
    try:
        return sorted(((n, int(v)) for n, v in items), key=lambda x: x[1])
    except TypeError:
        return items


def signal_hint(sig: str) -> str:
    m = re.match(r"\w+\((.*)\)$", sig)
    if not m or not m.group(1):
        return "(no arguments)"
    out = []
    for t in m.group(1).split(","):
        t = t.strip()
        base = re.sub(r"^const\s+|\s*[&*]$", "", t).strip()
        out.append(_CPP_PY.get(base, base))
    return "(" + ", ".join(out) + ")"


def list_members(cls, inherited: bool, grep: str | None) -> None:
    classes = [c for c in cls.__mro__ if c is not object] if inherited else [cls]
    rx = re.compile(grep, re.IGNORECASE) if grep else None
    seen: set[str] = set()
    groups: dict[str, list[str]] = {
        "signals": [],
        "methods": [],
        "enums / nested classes": [],
        "enum values (unscoped names; Qt 5 only, use the scoped enum)": [],
        "attributes": [],
    }
    for c in classes:
        for n, v in vars(c).items():
            if n.startswith("_") or n in seen:
                continue
            seen.add(n)
            if rx and not rx.search(n):
                continue
            origin = "" if c is cls else f"   [from {c.__name__}]"
            t = type(v).__name__
            if t in SIGNAL_TYPES:
                sigs = getattr(v, "signatures", None) or ()
                groups["signals"].append(
                    f"{n}: " + (" | ".join(sigs) if sigs else "?") + origin
                )
            elif inspect.isclass(v):
                label = "enum" if _is_enum(v) else "class"
                groups["enums / nested classes"].append(f"{n}  ({label}){origin}")
            elif callable(v) or t in _METHOD_TYPES:
                func = getattr(
                    c, n, v
                )  # the bound descriptor carries the SIP docstring
                sigs, _ = split_doc(
                    getattr(func, "__doc__", None)
                    or getattr(getattr(v, "__func__", v), "__doc__", None)
                )
                line = sigs[0] if sigs else f"{n}(...)"
                if len(sigs) > 1:
                    line += f"   (+{len(sigs) - 1} overloads)"
                groups["methods"].append(line + origin)
            elif isinstance(v, int) and not isinstance(v, bool):
                groups[
                    "enum values (unscoped names; Qt 5 only, use the scoped enum)"
                ].append(f"{n} = {int(v)}" + origin)
            else:
                groups["attributes"].append(f"{n} = {v!r}"[:100] + origin)
    for title, rows in groups.items():
        if rows:
            print(f"{title} ({len(rows)}):")
            for r in sorted(rows, key=str.lower):
                print("  " + r)


# --------------------------------------------------------------------------- source lookup
def _find_files(root: Path, sub: str, name: str) -> list[Path]:
    base = root / sub
    if not base.is_dir():
        return []
    return sorted(base.rglob(name))


def _git_grep(
    root: Path, pattern: str, paths: list[str], max_lines: int = 12
) -> list[str]:
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "grep",
                "-n",
                "-I",
                "-E",
                "-e",
                pattern,
                "--",
                *paths,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return r.stdout.splitlines()[:max_lines]


def _header_notes(lines: list[str], idx: int) -> list[str]:
    """Doxygen notes (\\since, \\deprecated, \\note, \\warning) in the comment block above line idx."""
    notes = []
    j = idx - 1
    while j >= 0 and j > idx - 40:
        s = lines[j].strip()
        if re.search(r"\\(since|deprecated|note|warning)\b", s):
            notes.append(s.lstrip("* "))
        if s.startswith("/**"):
            break
        if (
            s
            and not s.startswith("*")
            and not s.startswith("/")
            and not s.endswith("*/")
        ):
            break
        j -= 1
    return list(reversed(notes))


def source_hits(
    cls, member: str | None, qt6: bool, member_is_class: bool = False
) -> None:
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import pyqgis_env
    from qgis.core import Qgis

    top = cls.__name__
    is_qgis = top.startswith("Qgs") or top == "Qgis"
    qgis4 = Qgis.QGIS_VERSION_INT >= 40000
    if is_qgis:
        keys = ["QGIS4_SRC", "QGIS_SRC"] if qgis4 else ["QGIS_SRC", "QGIS4_SRC"]
    else:
        keys = ["QTBASE6_SRC", "QTBASE_SRC"] if qt6 else ["QTBASE_SRC", "QTBASE6_SRC"]
    found = pyqgis_env.resolve(keys, quick=True)
    key = next((k for k in keys if found[k]["value"]), None)
    print("source:")
    if key is None:
        print(
            f"  {keys[0]} is not set and was not found; run pyqgis_env.py (web docs are the fallback)."
        )
        return
    if key != keys[0]:
        print(
            f"  ({keys[0]} not found; showing {key}, a different major version - check \\since / \\deprecated)"
        )
    root_s = found[key]["value"]
    root = Path(root_s)
    base = top.lower()
    files = _find_files(root, "src", base + ".h") + _find_files(
        root, "src", base + ".cpp"
    )
    if is_qgis:
        # the Qt 5 and Qt 6 sip files are near-identical; show the one that matches this Python
        files += [
            f
            for f in _find_files(root, "python", base + ".sip.in")
            if ("PyQt6" in f.parts) == qt6
        ]
    if not files:
        hits = _git_grep(root, rf"^\s*class\s+(\w+_EXPORT\s+)?{top}\b", ["src"], 5)
        if not hits:
            print(f"  nothing named {base}.h under {root}; try find_source.py '{top}'")
            return
        files = [root / h.split(":", 1)[0] for h in hits]
    for f in files:
        rel = f.relative_to(root).as_posix()
        if not member:
            print(f"  {rel}")
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        # methods and signals: require "name(" so doc mentions are skipped; nested enums/classes: bare name
        rx = re.compile(
            rf"\b{re.escape(member)}\b"
            if member_is_class
            else rf"\b{re.escape(member)}\s*\("
        )
        limit = 4 if f.suffix == ".cpp" else 8
        shown = 0
        for i, line in enumerate(lines):
            if rx.search(line) and not line.strip().startswith(("*", "//", "/*")):
                print(f"  {rel}:{i + 1}: {line.strip()[:140]}")
                if f.suffix == ".h":
                    for n in _header_notes(lines, i):
                        print(f"      {n}")
                shown += 1
                if shown >= limit:
                    print(f"  {rel}: ... more hits; use find_source.py")
                    break
        if shown == 0:
            print(
                f"  {rel}: no line mentions {member} (inherited? check the base class)"
            )


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("name")
    ap.add_argument(
        "--members", action="store_true", help="list what the class really has"
    )
    ap.add_argument(
        "--inherited", action="store_true", help="with --members: include base classes"
    )
    ap.add_argument(
        "--grep", metavar="RX", help="with --members: only names matching this regex"
    )
    ap.add_argument(
        "--no-source", action="store_true", help="skip the source-file lookup"
    )
    a = ap.parse_args()

    from qgis.PyQt.QtCore import QT_VERSION_STR

    qt6 = QT_VERSION_STR.startswith("6")
    modname, obj, owner = resolve_name(a.name)
    attrs = a.name.split(".")
    kind = kind_of(obj)
    full = a.name if a.name.startswith(modname) else f"{modname}.{a.name}"
    print(f"{full}   [{kind}]   ({_versions()})")

    member = attrs[-1] if inspect.isclass(owner) else None
    cls = owner if inspect.isclass(owner) else (obj if inspect.isclass(obj) else None)
    if member and inspect.isclass(owner):
        d = defining_class(owner, member)
        if d is not None and d is not owner:
            print(
                f"defined in: {d.__module__}.{d.__name__}  (inherited by {owner.__name__})"
            )
        elif d is not None:
            print(f"defined in: {d.__name__}")

    if kind == "signal":
        sigs = getattr(obj, "signatures", None) or ()
        print("signal signatures (real C++ types; trust these over stubs):")
        for s in sigs:
            print(f"  {s}   -> slot receives {signal_hint(s)}")
        if len(sigs) > 1:
            print(
                "  overloaded: connect a specific one with signal[type].connect(slot)"
            )
        doc = getattr(obj, "__doc__", None)
        if (
            doc and doc != type(obj).__doc__
        ):  # unbound signals usually carry only the generic pyqtSignal doc
            _, text = split_doc(doc)
            if text:
                print("doc:\n  " + text.replace("\n", "\n  "))
        else:
            print(
                "doc: (not attached to the signal object; see the header / sip lines below)"
            )
    elif kind in ("class", "enum"):
        bases = [b for b in obj.__mro__[1:] if b is not object]
        if bases:
            print(
                "bases: "
                + " -> ".join(
                    f"{b.__module__.split('.')[-1]}.{b.__name__}" for b in bases[:6]
                )
            )
        sigs, text = split_doc(getattr(obj, "__doc__", None))
        if sigs:
            print("constructors:")
            for s in sigs:
                print("  " + s)
        if text:
            print("doc:\n  " + text.replace("\n", "\n  "))
        if kind == "enum":
            print("members:")
            for n, v in enum_members(obj):
                print(f"  {n} = {v}")
        elif a.members:
            list_members(obj, a.inherited, a.grep)
        else:
            print("(add --members to list signals, methods and nested enums)")
    elif kind == "method/function":
        sigs, text = split_doc(getattr(obj, "__doc__", None))
        if sigs:
            print("signatures:")
            for s in sigs:
                print("  " + s)
        else:
            try:
                print(f"signature: {obj.__name__}{inspect.signature(obj)}")
            except (TypeError, ValueError):
                print("signature: (not available)")
        if text:
            print("doc:\n  " + text.replace("\n", "\n  "))
    elif kind == "module":
        names = [n for n in dir(obj) if not n.startswith("_")]
        print(f"{len(names)} public names; first: " + ", ".join(names[:40]))
    else:
        print(f"value: {obj!r}  (type {type(obj).__name__})")

    if not a.no_source and cls is not None:
        source_hits(cls, member, qt6, member_is_class=inspect.isclass(obj))
    return 0


if __name__ == "__main__":
    sys.exit(main())
