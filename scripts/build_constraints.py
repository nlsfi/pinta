# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Build a component's runtime constraints file from the workspace lock."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import cast

from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
AIRFLOW_PATTERN = re.compile(r"apache-airflow(?:\[[^\]]+\])?==([^\s;]+)")


def uv_executable() -> str:
    """Return the uv executable or raise if it is unavailable."""
    executable = shutil.which("uv")
    if executable is None:
        msg = "uv must be available on PATH"
        raise FileNotFoundError(msg)
    return executable


def parse_pins(content: str, source: str) -> dict[str, str]:
    """Parse exact package pins and reject conflicting versions."""
    pins: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except ValueError as exc:
            msg = f"Expected an exact name==version pin in {source}: {line}"
            raise ValueError(msg) from exc

        if requirement.marker is not None:
            environment = cast("dict[str, str]", default_environment())
            environment.update(
                {
                    "python_version": "3.12",
                    "python_full_version": "3.12.0",
                }
            )
            if not requirement.marker.evaluate(environment):
                continue
        specifiers = list(requirement.specifier)
        if len(specifiers) != 1 or specifiers[0].operator != "==":
            msg = f"Expected an exact name==version pin in {source}: {line}"
            raise ValueError(msg)

        name = re.sub(r"[-_.]+", "-", requirement.name).lower()
        version = specifiers[0].version
        previous = pins.get(name)
        if previous is not None and previous != version:
            msg = f"Conflicting pins for {name} in {source}: {previous} and {version}"
            raise ValueError(msg)
        pins[name] = version
    return pins


def export_locked_constraints(package: str, extra: str | None) -> dict[str, str]:
    """Export exact runtime pins for one workspace package."""
    command = [
        uv_executable(),
        "export",
        "--package",
        package,
        "--locked",
        "--no-emit-workspace",
        "--no-hashes",
        "--no-header",
        "--no-default-groups",
    ]
    if extra is not None:
        command.extend(["--extra", extra])
    exported = subprocess.run(  # noqa: S603
        command,
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    return parse_pins(exported.stdout, "uv.lock export")


def get_airflow_version(project: dict[str, object]) -> str:
    """Return the exact Airflow version configured by the dags project."""
    dependencies = project["project"]["optional-dependencies"]["airflow"]  # type: ignore[index]
    for dependency in dependencies:
        match = AIRFLOW_PATTERN.search(dependency)
        if match is not None:
            return match.group(1)
    msg = "The dags airflow extra must pin apache-airflow with ==."
    raise ValueError(msg)


def get_airflow_constraints(version: str) -> dict[str, str]:
    """Download the modified upstream Airflow constraints file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "airflow-constraints.txt"
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(
                    ROOT
                    / "components/dags/src/pinta_dags/scripts"
                    / "prepare_airflow_constraints.py"
                ),
                "--airflow-version",
                version,
                "--python-version",
                "3.12",
                "--output",
                str(output),
            ],
            check=True,
            cwd=ROOT,
        )
        return parse_pins(output.read_text(), "modified Airflow constraints")


def build_constraints(
    module: str,
    extra: str | None,
    *,
    include_airflow_constraints: bool,
) -> Path:
    """Write the component's merged constraints file."""
    project = tomllib.loads((Path.cwd() / "pyproject.toml").read_text())
    package = project["project"]["name"]
    pins = export_locked_constraints(package, extra)

    if include_airflow_constraints:
        dags_project = tomllib.loads(
            (ROOT / "components/dags/pyproject.toml").read_text()
        )
        airflow_pins = get_airflow_constraints(get_airflow_version(dags_project))
        pins.update(airflow_pins)

    constraints_path = Path.cwd() / "src" / module / "constraints.txt"
    constraints_path.write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(pins.items()))
    )
    return constraints_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--extra")
    parser.add_argument("--airflow", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate a runtime constraints file."""
    args = parse_args(argv)
    path = build_constraints(
        args.module,
        args.extra,
        include_airflow_constraints=args.airflow,
    )
    print(f"Wrote constraints to {path}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
