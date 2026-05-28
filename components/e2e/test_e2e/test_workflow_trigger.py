# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest
import requests
from pinta_e2e_utils.airflow_client import AirflowClient, DagRun

HELLO_WORLD_TAG = "hello_world"
HELLO_WORLD_DAG_ID = "print_hello_world"
DAG_RUN_TIMEOUT_S = 300.0


@pytest.mark.xdist_group("airflow")
def test_print_hello_world_runs_to_success(
    backend_url: str,
    airflow_client: AirflowClient,
) -> None:
    response = requests.post(
        f"{backend_url}/workflows/{HELLO_WORLD_TAG}",
        json={"parameters": {"name": "Pinta"}},
        headers={"Accept-Language": "en"},
        timeout=30,
    )
    assert response.status_code == 202, response.text
    dag = DagRun.from_api(response.json())
    assert dag.id == HELLO_WORLD_DAG_ID
    assert dag.run_id.startswith("manual__")

    state = airflow_client.wait_for_dag_run(dag, timeout=DAG_RUN_TIMEOUT_S)
    assert state == "success", (
        f"DAG run finished with state={state}\n"
        f"{airflow_client.describe_failed_run(dag.id, dag.run_id)}"
    )


def test_workflow_endpoint_rejects_invalid_parameters(backend_url: str) -> None:
    response = requests.post(
        f"{backend_url}/workflows/{HELLO_WORLD_TAG}",
        json={"parameters": {"name": 42}},
        headers={"Accept-Language": "en"},
        timeout=30,
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail.startswith("Invalid workflow parameters:")
    assert "name" in detail
