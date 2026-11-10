# Software supply chain review (A03:2025)

Two different problems hide under "dependency risk", and they need different methods:

1. **Vulnerable dependencies**: honest packages with known bugs (CVEs). Found by matching
   versions against advisory databases. Mostly solved by tools (pip-audit, osv-scanner,
   Dependency-Track). Your job: run them, check reachability of the vulnerable function where
   feasible, and confirm a fixed version exists.
2. **Malicious dependencies**: packages that are hostile on purpose, through typosquatting,
   dependency confusion, a compromised maintainer account, or a compromised build pipeline. No
   CVE exists at the moment of attack. Found only by heuristics, provenance, hygiene and timing.
   This is where careful review adds value, and where its limits must be stated honestly.

## Contents

- How malicious Python packages execute
- Checks: inventory and hygiene
- Checks: known vulnerabilities
- Checks: malicious package indicators
- Checks: installed environment (import-time payloads)
- What this review cannot detect
- Recommendations to include

---

## How malicious Python packages execute

Knowing the execution points tells you where to look.

| When | Mechanism | Where to look |
| --- | --- | --- |
| Install / build | `setup.py` runs arbitrary code when building an sdist; custom build backends and PEP 517 hooks also run code | sdist contents, `setup.py`, `pyproject.toml` `[build-system]` |
| Interpreter start-up | `.pth` files in site-packages: any line starting with `import` is executed on every Python start, even if the package is never imported | `site-packages/*.pth` |
| Interpreter start-up | `sitecustomize.py` / `usercustomize.py` on the path | site-packages, user site |
| Import | Module-level code in `__init__.py` or any imported module | top-level statements |
| Tooling | Entry points auto-loaded by tools: pytest plugins (`pytest11`), Flake8/pylint plugins, Jupyter extensions, Airflow plugins, QGIS plugins | `*.dist-info/entry_points.txt` |
| Call | Payload in a commonly called function | function bodies |

The `.pth` and entry point mechanisms are the "activated when a dependency is loaded" class:
a developer running `python` or `pytest` triggers them without importing the package.

## Checks: inventory and hygiene

Read the dependency declarations: `pyproject.toml`, `requirements*.txt`, `uv.lock`,
`poetry.lock`, `Pipfile.lock`, `setup.cfg`, `environment.yml`, `constraints*.txt`.

Flag:

- **No lockfile** for an application (libraries may legitimately use ranges, applications should
  lock). Unpinned or range-only requirements in deployable services.
- **No hashes.** `uv.lock` and `poetry.lock` include hashes; `requirements.txt` should use
  `--hash` (via `uv pip compile --generate-hashes` or `pip-compile --generate-hashes`) and installs
  should use `--require-hashes`.
- **Dependency confusion risk.** `--extra-index-url` (pip and uv look for the best version
  across all indexes, so a public package with the same name as an internal one can win). Good:
  a single index (internal mirror/proxy) as `--index-url`, or uv `[[tool.uv.index]]` with
  `explicit = true` and per-package `[tool.uv.sources]` pinning for internal packages. Also check
  that internal package names are reserved or blocked upstream in the proxy.
- **Direct URL / VCS dependencies** (`git+https://...@main`, `https://.../pkg.zip`) without an
  immutable reference. Good: full commit SHA.
- **Unused dependencies** (declared but never imported): attack surface without value.
- **Typosquat candidates**: names one edit away from popular packages (`reqeusts`, `python-dateutil`
  vs `dateutil`, `beautifulsoup` vs `beautifulsoup4`), or with misleading prefixes/suffixes
  (`-python`, `py-`, `-utils`). Check unfamiliar names against PyPI: maintainer, age, download
  history, linked repository.
- **Abandoned or single-maintainer critical packages** (informational).

## Checks: known vulnerabilities

- Run pip-audit or osv-scanner (see the tool table in SKILL.md).
- For each Critical/High result: is the vulnerable code path used? Is there a fixed version, and
  does upgrading conflict with other pins? Report the minimal safe upgrade.
- Check end-of-life runtimes: the Python version itself, Django/Flask/FastAPI major versions,
  GDAL/PROJ versions bundled in containers.
- If a central SCA tool (e.g. Dependency-Track) already monitors the project, note that and keep
  this section brief.

## Checks: malicious package indicators

Use the bundled script and GuardDog where available. Then review leads manually (statically).

Indicators, roughly in order of signal strength:

- Network, subprocess or `exec`/`eval` calls at module level (import-time side effects).
- `base64`/`zlib`/`marshal`/`codecs` decoding followed by `exec`/`eval`/`compile`.
- Very long lines or large high-entropy string literals (obfuscation).
- Reading credential locations at import: `~/.ssh`, `~/.aws`, `~/.config/gcloud`, `.netrc`,
  `.pypirc`, `.git-credentials`, browser profiles, environment variable dumps (`os.environ` sent
  anywhere), CI tokens (`GITHUB_TOKEN`, `CI_JOB_TOKEN`).
- Network destinations that are not the package's stated purpose: raw IPs, paste sites, Discord/
  Telegram webhooks, newly registered domains.
- `.pth` files with `import` lines from packages that have no reason to need one.
- Install-time code in `setup.py` beyond normal metadata (downloads, subprocess, writing outside
  the build dir).
- **Version timing**: a version released in the last few days (most malicious releases are found
  and yanked within days); a sudden release from a long-dormant package; a version on PyPI with
  no matching tag in the source repository.
- **Provenance**: whether the package publishes PyPI attestations (PEP 740, Trusted Publishing).
  Absence is not evidence of malice, but presence links the artefact to a source repo and CI run.

Legitimate `.pth` files you will commonly see: `distutils-precedence.pth` (setuptools),
`_virtualenv.pth`, `__editable__.*.pth` and `*.pth` from editable installs, `coverage`/
`pytest-cov` subprocess hooks, `pywin32.pth`, `matplotlib` namespace `*-nspkg.pth`. Still
read them; do not just trust the name.

**Do not install or import a suspicious package to "check it".** To inspect a package that is
not installed, fetch the wheel file directly from the index URL (wheels are zip files and do not
execute on download) and unzip it to a scratch directory. Avoid `pip download` for sdists: it may
build metadata by running `setup.py`.

When an indicator is found, report it as *Needs verification* with the exact file and line, and
recommend: freeze installs, compare against the source repository at the matching tag, check the
package's PyPI page and advisories (OSV, GitHub Security Advisories), and if confirmed, treat
machines that installed it as compromised (rotate credentials accessible from them).

## Checks: installed environment (import-time payloads)

If a project venv exists (`.venv`), the bundled script scans its site-packages for `.pth`
executable lines, `sitecustomize`/`usercustomize`, module-level dangerous calls and obfuscation.
Also check:

- `*.dist-info/entry_points.txt` for `pytest11`, `console_scripts` overriding common names, and
  plugin groups the project's tools auto-load.
- `*.dist-info/RECORD` vs. files on disk, if tampering is suspected.
- Packages present in the venv but absent from the lockfile (installed ad hoc, drift).

## What this review cannot detect

State these in the report under "Not covered" when relevant:

- A malicious release published after the review, or a payload that is well hidden, delayed,
  or environment-triggered (only on CI, only on certain hostnames).
- Compromises in transitive build tooling (compilers, build backends) or the package index itself.
- Behaviour of native extensions (`.pyd`, `.so`) beyond strings inspection.
- Anything in dependencies not installed locally or not present in the lockfile.

Static review reduces risk; it does not certify dependencies as safe. Process controls do most
of the work, which is why the recommendations below matter.

## Recommendations to include

Tailor to what is missing:

- **Release cooldown**: do not adopt versions younger than N days (e.g. 7). uv supports
  `exclude-newer`; some artefact proxies (for example JFrog Curation in front of Artifactory)
  can block package versions younger than a set age. Enforcing it centrally beats per-repo
  settings.
- **Lock with hashes** and install with `--require-hashes` / `uv sync --locked` in CI.
- **Single trusted index** through the internal proxy; no `--extra-index-url`; reserve internal
  names.
- **Pin CI actions, pre-commit hooks and container images by digest/SHA**, not tags.
- **Continuous SCA** (pip-audit in CI or Dependency-Track with SBOM upload).
- **Least-privilege developer and CI environments**: credentials scoped and short-lived, so a
  malicious dependency running in a dev shell has less to steal.
- **Review dependency additions** in PRs: new dependencies get a human check of name, maintainer,
  age and necessity.
