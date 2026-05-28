# E2E test component

## Parallel execution

Tests run under `pytest-xdist` with `--dist loadgroup`. Because all workers
share a single Airflow instance, mark any test that triggers a DAG with
`@pytest.mark.xdist_group("airflow")` so these tests run serially on one worker.
