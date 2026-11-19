# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Install a built component wheel in a clean environment and check dependencies."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def check_wheel(
    module: str,
    extra: str | None,
    wheel_dir: Path,
    find_links: list[Path],
) -> None:
    """Install the project wheel using its constraints and run uv pip check."""
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"Expected exactly one wheel in {wheel_dir}, found {len(wheels)}"
        raise RuntimeError(msg)

    requirement = str(wheels[0].resolve())
    if extra is not None:
        requirement = f"{requirement}[{extra}]"
    constraint = Path("src", module, "constraints.txt").resolve()
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv must be available on PATH"
        raise FileNotFoundError(msg)

    with tempfile.TemporaryDirectory() as temp_dir:
        environment = Path(temp_dir) / "wheel-check"
        subprocess.run(  # noqa: S603
            [uv, "venv", "--python", "3.12", str(environment)], check=True
        )
        python = environment / "bin/python"
        command = [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--constraint",
            str(constraint),
        ]
        for find_link in find_links:
            command.extend(["--find-links", str(find_link)])
        command.append(requirement)
        subprocess.run(command, check=True)  # noqa: S603
        subprocess.run(  # noqa: S603
            [uv, "pip", "check", "--python", str(python)], check=True
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--extra")
    parser.add_argument("--wheel-dir", type=Path, default=Path("dist"))
    parser.add_argument("--find-links", type=Path, action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate the built component wheel."""
    args = parse_args(argv)
    check_wheel(args.module, args.extra, args.wheel_dir, args.find_links)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
