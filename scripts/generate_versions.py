# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Generate local component versions from source package metadata."""

import argparse
import json
import tempfile
import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_SOURCES = {
    "processing_image_tag": "processing",
    "backend_image_tag": "backend",
    "qgis_plugin_version": "qgis_plugin",
    "dags_version": "dags",
    "db_version": "db",
}


def generate_versions(root_dir: Path) -> dict[str, str]:
    """Read each component's project version into the deployment's JSON keys."""
    versions = {}
    for key, component in VERSION_SOURCES.items():
        project_file = root_dir / "components" / component / "pyproject.toml"
        with project_file.open("rb") as source:
            version = tomllib.load(source)["project"]["version"]
        if not isinstance(version, str):
            message = f"Invalid project version in {project_file}"
            raise TypeError(message)
        versions[key] = version
    return versions


def main() -> None:
    """Write the local version file without exposing partial writes to readers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "version.json")
    parser.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    args = parser.parse_args()
    output = args.output
    versions = generate_versions(args.root_dir)

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        json.dump(versions, temporary_file, indent=2)
        temporary_file.write("\n")
    try:
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
