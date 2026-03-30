# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import os
import shutil
import sqlite3
from pathlib import Path
from tempfile import mkdtemp

import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--use-temp-airflow-home",
        action="store_true",
        # Use temp dir by default on CI
        default="CI" in os.environ,
        help="Use a temporary path for AIRFLOW_HOME for tests",
    )


def pytest_configure(config: pytest.Config):
    worker_id = getattr(config, "workerinput", {}).get("workerid", "master")

    if os.environ.get("AIRFLOW_HOME") and worker_id == "master":
        return

    airflow_home_dir = Path(__file__).parent.parent.joinpath(".airflow")
    airflow_home_dir.mkdir(exist_ok=True)

    if config.getoption("--use-temp-airflow-home"):
        os.environ["AIRFLOW_HOME"] = mkdtemp(prefix=f".{worker_id}-airflow-test")
    else:
        os.environ["AIRFLOW_HOME"] = str(
            airflow_home_dir / f".{worker_id}-airflow-test"
        )


@pytest.fixture(scope="session", autouse=True)
def _initialize_airflow() -> None:
    from airflow.utils.db import initdb

    shutil.rmtree(os.environ["AIRFLOW_HOME"])
    Path(os.environ["AIRFLOW_HOME"]).mkdir(exist_ok=True)

    initdb()

    with sqlite3.connect(Path(os.environ["AIRFLOW_HOME"]) / "airflow.db") as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO dag_bundle (name) VALUES ('mock-dags')")
