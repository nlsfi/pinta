<!-- markdownlint-disable MD041 -->
See root AGENTS.md for shared conventions.

# Agent Instructions — dags

Apache Airflow DAGs (`src/pinta_dags/dags/`), shared tasks (`tasks.py`),
sensors and config. DAGs orchestrate the processing container.

Load `nls-airflow` before editing DAGs, tasks or sensors.

## Rules

- Any task that touches a database must use
  `@task.docker(**config.PINTA_CONTAINER_TASK_ARGS)`; database URLs only
  resolve inside containers.
- Import `pinta_*`, SQLAlchemy and other heavy modules inside the task
  function, not at module level (ruff TID253 enforces this for DAG modules).
- Do not use `logging` in DAG modules (ruff TID251).
- Airflow is an optional extra (`airflow`); the published package must not
  pin an Airflow version in its base dependencies.
- `numpy` and `scipy` are pinned in the `airflow` extra. Follow
  "Updating Airflow" in the README for upgrades.

## Tests

- `uv run pytest test_dags` (needs the `airflow` extra, installed by
  `make sync` at the repo root).
- After DAG changes against a running Airflow: `make airflow-reserialize`.
