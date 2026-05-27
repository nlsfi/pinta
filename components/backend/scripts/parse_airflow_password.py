# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import argparse
import json
from pathlib import Path

ENV_KEY = "PINTA_BACKEND_AIRFLOW_PASSWORD"


def update_env_file(env_file: Path, key: str, value: str) -> None:  # noqa: D103
    prefix = f"{key}="
    lines = env_file.read_text().splitlines()
    matches = [line.startswith(prefix) for line in lines]
    lines = [
        f"{prefix}{value}" if match else line
        for line, match in zip(lines, matches, strict=True)
    ]

    if not any(matches):
        lines.append(f"{prefix}{value}")

    env_file.write_text("\n".join(lines) + "\n")


def parse_airflow_password(password_file: Path, username: str) -> str:  # noqa: D103
    with password_file.open() as file:
        passwords = json.load(file)

    return passwords[username]


def main() -> None:  # noqa: D103
    parser = argparse.ArgumentParser()
    parser.add_argument("password_file", type=Path)
    parser.add_argument("username")
    parser.add_argument("env_file", type=Path)
    args = parser.parse_args()

    password = parse_airflow_password(args.password_file, args.username)
    update_env_file(args.env_file, ENV_KEY, password)
    print(password)  # noqa: T201


if __name__ == "__main__":
    main()
