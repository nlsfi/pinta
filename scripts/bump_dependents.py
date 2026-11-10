# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Raise version requirements of components that depend on a released component.

Prints the names of the changed dependent components, one per line.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

COMPONENTS_DIR = Path(__file__).parent.parent / "components"
REQUIREMENT_TABLES = ("[project]", "[project.optional-dependencies]")
# Matches e.g. "pinta-db", "pinta-db[psycopg]" or "pinta-db>=1.0.0,<2"
REQUIREMENT_PATTERN = re.compile(
    r'"([A-Za-z0-9_.-]+)(\[[^\]]*\])?(?:\s*[<>=!~][^"]*)?"'
)


def normalize(name: str) -> str:
    """Return the PEP 503 normalized package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def package_name(component: str) -> str:
    """Return the normalized package name of a component."""
    with (COMPONENTS_DIR / component / "pyproject.toml").open("rb") as file:
        return normalize(tomllib.load(file)["project"]["name"])


def version_range(version: str) -> str:
    """Return a bound that allows the version and compatible later releases.

    Breaking changes only bump the minor version while the major version is zero.
    """
    major, minor, *_ = (int(part) for part in version.split("."))
    upper = f"{major + 1}" if major else f"0.{minor + 1}"
    return f">={version},<{upper}"


def bump_requirements(text: str, dependency: str, version: str) -> str:
    """Set the version range of the dependency in the project requirements."""

    def replace(match: re.Match[str]) -> str:
        name, extras = match.group(1), match.group(2) or ""
        if normalize(name) != dependency:
            return match.group(0)
        return f'"{name}{extras}{version_range(version)}"'

    table = ""
    lines = []
    for line in text.splitlines(True):  # noqa: FBT003
        if line.startswith("["):
            table = line.strip()
        if table in REQUIREMENT_TABLES and not line.startswith("["):
            lines.append(REQUIREMENT_PATTERN.sub(replace, line))
        else:
            lines.append(line)
    return "".join(lines)


def main() -> None:
    """Bump the requirements and print the changed components."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", help="Released component directory name.")
    parser.add_argument("version", help="Released version.")
    args = parser.parse_args()

    dependency = package_name(args.component)
    for path in sorted(COMPONENTS_DIR.glob("*/pyproject.toml")):
        if path.parent.name == args.component:
            continue
        text = path.read_text()
        new_text = bump_requirements(text, dependency, args.version)
        if new_text != text:
            path.write_text(new_text)
            sys.stdout.write(f"{path.parent.name}\n")


if __name__ == "__main__":
    main()
