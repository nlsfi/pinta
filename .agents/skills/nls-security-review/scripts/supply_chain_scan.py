#!/usr/bin/env python
"""Static supply chain checks for a Python repository.

Standard library only, so it can run before any third-party tooling is trusted.
It never imports, installs or executes the packages it inspects.

Checks:
  1. Dependency declarations: lockfiles, pins, hashes, extra indexes, VCS/URL deps.
  2. Release age of pinned versions (cooldown) and yanked versions, via the PyPI JSON API.
  3. Installed environment (site-packages): executable .pth lines, sitecustomize/usercustomize,
     auto-loaded pytest plugins, module-level network/process/exec calls, obfuscated code.

All results are leads for manual review, not verdicts. Exit code is 0 unless the script fails.

Usage (PowerShell):
  python supply_chain_scan.py --repo . --cooldown-days 7
  python supply_chain_scan.py --repo . --no-network --format json
  python supply_chain_scan.py --site-packages /path/to/.venv/Lib/site-packages
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox", ".nox",
             ".mypy_cache", ".ruff_cache", ".pytest_cache", "build", "dist", "site-packages"}
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
REQ_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*==\s*([^\s;,#\\]+)")
REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
BASE64ISH_RE = re.compile(r"[A-Za-z0-9+/=_-]{400,}")

BENIGN_PTH_PATTERNS = [
    re.compile(r"^distutils-precedence\.pth$"),
    re.compile(r"^_virtualenv\.pth$"),
    re.compile(r"^__editable__\..*\.pth$"),
    re.compile(r"^_.*_editable.*\.pth$"),
    re.compile(r".*-nspkg\.pth$"),
    re.compile(r"^pywin32\.pth$"),
    re.compile(r"^pytest-cov\.pth$"),
    re.compile(r"^coverage.*\.pth$"),
]

# Module-level calls worth a look. Matched against resolved dotted names.
SUSPICIOUS_EXACT = {
    "exec", "eval", "compile", "builtins.exec", "builtins.eval",
    "marshal.loads", "pickle.loads", "os.system", "os.popen", "os.startfile", "pty.spawn",
    "socket.socket", "socket.create_connection",
    "urllib.request.urlopen", "urllib.request.urlretrieve",
    "http.client.HTTPConnection", "http.client.HTTPSConnection",
    "requests.get", "requests.post", "requests.put", "requests.request", "requests.Session",
    "httpx.get", "httpx.post", "httpx.Client", "httpx.request",
}
SUSPICIOUS_PREFIXES = ("subprocess.", "os.exec", "os.spawn")
DECODER_NAMES = ("b64decode", "b32decode", "b85decode", "a85decode", "decompress",
                 "unhexlify", "fromhex", "loads", "rot13", "decode")


@dataclass
class Finding:
    check: str
    severity: str  # high | medium | low | info
    location: str
    message: str
    detail: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pinned: dict[str, str] = field(default_factory=dict)

    def add(self, *args, **kwargs) -> None:
        self.findings.append(Finding(*args, **kwargs))


def iter_files(root: Path, patterns: list[str]):
    for pattern in patterns:
        for path in root.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
                continue
            if path.is_file():
                yield path


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------- declarations

def check_requirements(root: Path, report: Report) -> None:
    files = list(iter_files(root, ["requirements*.txt", "requirements/*.txt", "constraints*.txt"]))
    for path in files:
        loc = rel(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        # Join backslash continuations so --hash lines belong to their requirement.
        logical = re.sub(r"\\\r?\n", " ", text).splitlines()
        reqs = 0
        hashed = 0
        for raw in logical:
            line = raw.split(" #", 1)[0].strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("--extra-index-url", "--extra_index_url")):
                report.add("dependency-confusion", "high", loc,
                           "--extra-index-url: packages may resolve from either index",
                           line)
                continue
            if line.startswith("--trusted-host"):
                report.add("index-config", "medium", loc,
                           "--trusted-host disables TLS verification for that host", line)
                continue
            if line.startswith("-"):
                continue
            reqs += 1
            if "--hash=" in line:
                hashed += 1
            if line.startswith(("git+", "hg+", "svn+", "bzr+")) or " @ git+" in line:
                if not SHA_RE.search(line):
                    report.add("vcs-dependency", "medium", loc,
                               "VCS dependency not pinned to a full commit SHA", line[:200])
                continue
            if "://" in line:
                report.add("url-dependency", "low", loc,
                           "Direct URL dependency; ensure it is immutable and hash-checked",
                           line[:200])
                continue
            match = REQ_PIN_RE.match(line)
            if match:
                report.pinned.setdefault(normalise(match.group(1)), match.group(3))
            elif REQ_NAME_RE.match(line):
                report.add("unpinned", "low", loc, "Requirement not pinned with ==",
                           line[:200])
        if reqs and hashed < reqs:
            report.add("no-hashes", "low", loc,
                       f"{reqs - hashed} of {reqs} requirements lack --hash; "
                       "installs cannot use --require-hashes")


def check_lockfiles(root: Path, report: Report) -> None:
    locks = {p.name: p for p in iter_files(root, ["uv.lock", "poetry.lock", "Pipfile.lock",
                                                     "pdm.lock", "pylock*.toml"])}
    has_pyproject = (root / "pyproject.toml").is_file()
    if not locks and not any(iter_files(root, ["requirements*.txt"])):
        if has_pyproject:
            report.add("no-lockfile", "medium", "pyproject.toml",
                       "No lockfile found; builds resolve whatever is newest at install time")
        return
    if tomllib is None:
        report.notes.append("Python < 3.11: TOML lockfiles not parsed.")
        return
    for name, path in locks.items():
        loc = rel(path, root)
        if name == "Pipfile.lock":
            data = json.loads(path.read_text(encoding="utf-8"))
            for section in ("default", "develop"):
                for pkg, info in data.get(section, {}).items():
                    ver = str(info.get("version", "")).lstrip("=")
                    if ver:
                        report.pinned.setdefault(normalise(pkg), ver)
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report and continue
            report.notes.append(f"Could not parse {loc}: {exc}")
            continue
        for pkg in data.get("package", data.get("packages", [])):
            pname, ver = pkg.get("name"), pkg.get("version")
            source = pkg.get("source", {}) if isinstance(pkg.get("source"), dict) else {}
            if "git" in source and not SHA_RE.search(str(source["git"])):
                report.add("vcs-dependency", "medium", loc,
                           f"{pname}: git source without full commit SHA", str(source["git"]))
            if "url" in source:
                report.add("url-dependency", "low", loc, f"{pname}: direct URL source",
                           str(source["url"]))
            non_registry = {"git", "url", "editable", "virtual", "directory", "path"}
            if non_registry & source.keys():
                continue  # VCS, URL or local source: not on the package index
            if pname and ver:
                report.pinned.setdefault(normalise(pname), str(ver))


def check_index_config(root: Path, report: Report) -> None:
    candidates = list(iter_files(root, ["pyproject.toml", "uv.toml", "pip.conf", "pip.ini",
                                         "setup.cfg", "tox.ini", "Dockerfile*", "Containerfile*",
                                         "Jenkinsfile*", "*.yml", "*.yaml"]))
    pattern = re.compile(r"extra[-_]index[-_]url", re.IGNORECASE)
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                report.add("dependency-confusion", "high", f"{rel(path, root)}:{lineno}",
                           "Extra package index configured; internal names could be shadowed "
                           "by public packages", line.strip()[:200])


# ---------------------------------------------------------------- release age

def fetch_release(index: str, name: str, version: str, timeout: float):
    url = f"{index.rstrip('/')}/{name}/{version}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "nls-security-review/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed scheme
            return name, version, json.load(resp), None
    except urllib.error.HTTPError as exc:
        return name, version, None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return name, version, None, str(exc)


def check_release_age(report: Report, index: str, cooldown_days: int, workers: int) -> None:
    if not report.pinned:
        report.notes.append("No pinned versions found; release-age check skipped.")
        return
    if not index.startswith("https://"):
        report.notes.append("Index JSON URL must be https; release-age check skipped.")
        return
    now = datetime.now(timezone.utc)
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(lambda kv: fetch_release(index, kv[0], kv[1], 15),
                           sorted(report.pinned.items()))
        for name, version, data, err in results:
            if err:
                errors.append(f"{name}=={version}: {err}")
                continue
            files = data.get("urls", [])
            times = [f.get("upload_time_iso_8601") for f in files if f.get("upload_time_iso_8601")]
            if any(f.get("yanked") for f in files):
                reason = next((f.get("yanked_reason") for f in files if f.get("yanked")), "")
                report.add("yanked", "high", f"{name}=={version}",
                           "Pinned version is yanked on the index", reason or "")
            if not times:
                continue
            first = min(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)
            age = (now - first).days
            if age < cooldown_days:
                report.add("cooldown", "medium", f"{name}=={version}",
                           f"Released {age} day(s) ago (cooldown {cooldown_days}); "
                           "review before adopting", first.isoformat())
    if errors:
        report.notes.append(f"Release lookup failed for {len(errors)} package(s), e.g. "
                            + "; ".join(errors[:5]))
    report.notes.append(f"Release age checked for {len(report.pinned)} pinned package(s) "
                        f"against {index}.")


# ---------------------------------------------------------------- installed env

def find_site_packages(root: Path) -> list[Path]:
    found = []
    for venv in (".venv", "venv", "env"):
        base = root / venv
        if not (base / "pyvenv.cfg").is_file():
            continue
        win = base / "Lib" / "site-packages"
        if win.is_dir():
            found.append(win)
        found.extend(p for p in (base / "lib").glob("python*/site-packages") if p.is_dir())
    return found


def check_pth(site: Path, report: Report) -> None:
    for pth in sorted(site.glob("*.pth")):
        lines = pth.read_text(encoding="utf-8", errors="replace").splitlines()
        executable = [ln for ln in lines if ln.lstrip().startswith(("import ", "import\t"))]
        if not executable:
            continue
        benign = any(p.match(pth.name) for p in BENIGN_PTH_PATTERNS)
        sev = "info" if benign else "high"
        note = "known pattern, still verify content" if benign else "unrecognised"
        report.add("pth-exec", sev, str(pth),
                   f".pth file runs code at every interpreter start ({note})",
                   " | ".join(ln.strip()[:300] for ln in executable[:3]))


def check_customize(site: Path, report: Report) -> None:
    for name in ("sitecustomize.py", "usercustomize.py"):
        path = site / name
        if path.exists():
            report.add("startup-hook", "high", str(path),
                       f"{name} runs at interpreter start; confirm it is expected")


def check_entry_points(site: Path, report: Report) -> None:
    for ep in site.glob("*.dist-info/entry_points.txt"):
        text = ep.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\[pytest11\]", text, re.MULTILINE):
            report.add("autoload-plugin", "info", str(ep),
                       "Registers a pytest plugin (auto-loaded when pytest runs)")


def _alias_map(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
    return aliases


def _dotted(node: ast.AST) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _resolve(name: str, aliases: dict[str, str]) -> str:
    head, _, tail = name.partition(".")
    if head in aliases:
        return aliases[head] + ("." + tail if tail else "")
    return name


def _module_level_nodes(body):
    """Yield statements that execute at import, descending into if/try/with but not defs."""
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.If):
            if any(isinstance(n, ast.Constant) and n.value == "__main__"
                   for n in ast.walk(stmt.test)):
                continue  # if __name__ == "__main__" (also inside and/or conditions)
            yield from _module_level_nodes(stmt.body)
            yield from _module_level_nodes(stmt.orelse)
        elif isinstance(stmt, ast.Try):
            for block in (stmt.body, stmt.orelse, stmt.finalbody):
                yield from _module_level_nodes(block)
            for handler in stmt.handlers:
                yield from _module_level_nodes(handler.body)
        elif isinstance(stmt, (ast.With, ast.For, ast.While)):
            yield from _module_level_nodes(stmt.body)
        else:
            yield stmt


def _calls_outside_defs(node: ast.AST):
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(cur, ast.Call):
            yield cur
        stack.extend(ast.iter_child_nodes(cur))


def scan_python_file(path: Path, report: Report, max_bytes: int) -> None:
    try:
        if path.stat().st_size > max_bytes:
            return
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for lineno, line in enumerate(source.splitlines(), 1):
        if len(line) > 2000 and BASE64ISH_RE.search(line):
            report.add("obfuscation", "medium", f"{path}:{lineno}",
                       f"Very long encoded-looking line ({len(line)} chars)", line[:120] + "...")
            break
    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return
    aliases = _alias_map(tree)
    for stmt in _module_level_nodes(tree.body):
        for call in _calls_outside_defs(stmt):
            name = _dotted(call.func)
            if not name:
                continue
            full = _resolve(name, aliases)
            if full in SUSPICIOUS_EXACT or full.startswith(SUSPICIOUS_PREFIXES):
                segment = ast.get_source_segment(source, call) or ""
                report.add("import-time-call", "medium", f"{path}:{call.lineno}",
                           f"Module-level call to {full} runs on import", segment[:200])
    # exec/eval of decoded data anywhere in the file
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name and _resolve(name, aliases) in ("exec", "eval", "builtins.exec", "builtins.eval"):
                inner = [_dotted(c.func) or "" for c in ast.walk(node) if isinstance(c, ast.Call)]
                if any(i.endswith(DECODER_NAMES) for i in inner[1:]):
                    report.add("exec-decoded", "high", f"{path}:{node.lineno}",
                               "exec/eval of decoded or decompressed data (obfuscation pattern)")


def check_site_packages(site: Path, report: Report, max_bytes: int, code_scan: bool) -> None:
    check_pth(site, report)
    check_customize(site, report)
    check_entry_points(site, report)
    if not code_scan:
        return
    count = 0
    for py in site.rglob("*.py"):
        scan_python_file(py, report, max_bytes)
        count += 1
    report.notes.append(f"Scanned {count} Python files in {site}.")


# ---------------------------------------------------------------- output

ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def render_markdown(report: Report) -> str:
    out = ["# Supply chain scan", ""]
    counts = {s: sum(1 for f in report.findings if f.severity == s) for s in ORDER}
    out.append("Leads for manual review, not verdicts. "
               + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    out.append("")
    by_check: dict[str, list[Finding]] = {}
    for f in sorted(report.findings, key=lambda f: (ORDER[f.severity], f.check, f.location)):
        by_check.setdefault(f.check, []).append(f)
    for check, items in by_check.items():
        out.append(f"## {check} ({len(items)})")
        for f in items[:200]:
            line = f"- **{f.severity}** `{f.location}`: {f.message}"
            if f.detail:
                line += f"  \n  `{f.detail.replace('`', chr(39))}`"
            out.append(line)
        if len(items) > 200:
            out.append(f"- ... {len(items) - 200} more")
        out.append("")
    if report.notes:
        out.append("## Notes")
        out.extend(f"- {n}" for n in report.notes)
    return "\n".join(out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="Repository root (default: .)")
    ap.add_argument("--site-packages", action="append", default=[],
                    help="site-packages dir to scan (repeatable). Default: repo .venv/venv")
    ap.add_argument("--cooldown-days", type=int, default=7)
    ap.add_argument("--index-json-url", default="https://pypi.org/pypi",
                    help="Base URL of a PyPI-compatible JSON API")
    ap.add_argument("--no-network", action="store_true", help="Skip release-age lookups")
    ap.add_argument("--no-code-scan", action="store_true",
                    help="Skip AST scan of installed packages (faster)")
    ap.add_argument("--max-file-kb", type=int, default=2048)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--format", choices=("md", "json"), default="md")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    report = Report()
    check_requirements(root, report)
    check_lockfiles(root, report)
    check_index_config(root, report)

    if args.no_network:
        report.notes.append("--no-network: release-age and yanked checks skipped.")
    else:
        check_release_age(report, args.index_json_url, args.cooldown_days, args.workers)

    sites = [Path(p) for p in args.site_packages] or find_site_packages(root)
    if not sites:
        report.notes.append("No virtual environment found; installed-package checks skipped. "
                            "Pass --site-packages to scan one.")
    for site in sites:
        check_site_packages(site, report, args.max_file_kb * 1024, not args.no_code_scan)

    if args.format == "json":
        print(json.dumps({"findings": [asdict(f) for f in report.findings],
                          "notes": report.notes}, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
