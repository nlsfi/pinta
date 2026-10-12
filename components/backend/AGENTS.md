<!-- markdownlint-disable MD041 -->
See root AGENTS.md for shared conventions.

# Agent Instructions — backend

FastAPI service (port 3011). Reads the databases through `pinta_db` and
triggers and monitors Airflow DAG runs through `apache-airflow-client`.

## Structure

- `app.py`, `routes.py`: app and endpoints; business logic in `services/`.
- `airflow_client.py`, `airflow_auth.py`: the only place that talks to Airflow.
- `settings.py`: pydantic-settings; Airflow fields accept both
  `PINTA_BACKEND_AIRFLOW_*` and bare `AIRFLOW_*` names; keep both aliases.
- `pinta_backend_test_utils/`: test stubs (e.g. stub Airflow); never import
  from production code.

## Rules

- Mark user-facing strings with `from pinta_backend.i18n import _` and use
  exactly `_`; extraction ignores other names. Update with `make backend-ts`
  and compile with `make backend-tc` from the repo root.
- Run locally with `make backend-start` (repo root); it generates
  `version.json` and stops the Compose backend container.

## Tests

- Unit: `uv run pytest test_backend`
- Integration (databases up and migrated): `uv run pytest test_integration_backend`
