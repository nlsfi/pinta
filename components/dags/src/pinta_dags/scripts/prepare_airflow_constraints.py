# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Download Apache Airflow constraints and remove managed package pins.

The modified constraints file is used during dependency updates so the workspace
can control the numpy and scipy pins separately from the upstream Airflow
constraints.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

_CONSTRAINTS_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/apache/airflow/constraints-{airflow_version}/"
    "constraints-{python_version}.txt"
)
_MANAGED_PACKAGES = ("numpy", "scipy")


@dataclass(frozen=True)
class ConstraintsRewriteResult:
    """Result of rewriting a constraints file."""

    managed_versions: dict[str, str]
    content: str


def build_constraints_url(airflow_version: str, python_version: str) -> str:
    """Return the official Airflow constraints URL for the given versions."""
    return _CONSTRAINTS_URL_TEMPLATE.format(
        airflow_version=airflow_version,
        python_version=python_version,
    )


def download_constraints(url: str) -> str:
    """Fetch a constraints file from `url`."""
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310
            return response.read().decode("utf-8")
    except URLError as exc:
        msg = f"failed to download Airflow constraints from {url}"
        raise RuntimeError(msg) from exc


def rewrite_constraints(constraints_text: str) -> ConstraintsRewriteResult:
    """Remove managed package pins and return the rewritten constraints text."""
    lines = constraints_text.splitlines()
    managed_versions: dict[str, str] = {}
    rewritten_lines: list[str] = []

    for line in lines:
        matched_package = next(
            (
                package
                for package in _MANAGED_PACKAGES
                if line.startswith(f"{package}==")
            ),
            None,
        )
        if matched_package is None:
            rewritten_lines.append(line)
            continue

        version = line.removeprefix(f"{matched_package}==")
        if matched_package in managed_versions:
            msg = (
                f"Airflow constraints file contains more than one {matched_package} pin"
            )
            raise ValueError(msg)
        managed_versions[matched_package] = version

    missing_packages = [
        package for package in _MANAGED_PACKAGES if package not in managed_versions
    ]
    if missing_packages:
        missing_list = ", ".join(missing_packages)
        msg = f"Airflow constraints file does not contain a pin for: {missing_list}"
        raise ValueError(msg)

    rewritten = "\n".join(rewritten_lines)
    if constraints_text.endswith("\n"):
        rewritten += "\n"
    return ConstraintsRewriteResult(
        managed_versions=managed_versions, content=rewritten
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Download an Airflow constraints file and remove the numpy pin so the "
            "workspace can control it separately."
        ),
    )
    parser.add_argument("--airflow-version", required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--constraints-url")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    args = parse_args(argv)
    constraints_url = args.constraints_url or build_constraints_url(
        args.airflow_version,
        args.python_version,
    )
    rewritten = rewrite_constraints(download_constraints(constraints_url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rewritten.content)
    for package in _MANAGED_PACKAGES:
        print(f"{package}=={rewritten.managed_versions[package]}")  # noqa: T201
    print(f"Wrote modified constraints to {args.output}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
