# Agent Instructions — pinta

## Purpose

Pinta builds a reference terrain model from new laser-scanning point clouds, lets users review and approve terrain changes in QGIS, and applies the accepted changes to the national 2 m elevation model (National Land Survey of Finland).

## Components

All components are members of one uv workspace (single `.venv`, single `uv.lock`, Python 3.12–3.13).

| Directory | Purpose | Language/framework |
| --- | --- | --- |
| `components/lib` | Shared utilities, settings, feature flags (`pinta_common`) | Python |
| `components/db` | Models and Alembic migrations for the primary and job databases | SQLModel, GeoAlchemy2, PostGIS |
| `components/processing` | Point cloud and raster processing, run in a container | laspy, rasterio, geopandas |
| `components/dags` | Workflow orchestration | Apache Airflow |
| `components/backend` | REST API that triggers and monitors DAG runs | FastAPI |
| `components/qgis_plugin` | Review and approval UI (GPLv3) | PyQGIS |
| `components/e2e` | End-to-end tests across all components | pytest |

## Cross-component rules

- import-linter enforces the layers `e2e : dags` → `qgis_plugin` → `processing : backend` → `db` → `lib`, and bans `*_test_utils` imports from production code. Never import upward.
- When changing `lib` or `db`, run `make test` (all components depend on them).
- When changing DB models, add a migration in `components/db` and check the backend, processing and QGIS plugin queries that use the model.
- When changing a `pinta_processing.scripts` function, update the DAG tasks that call it.
- When upgrading Airflow, keep `apache-airflow-client` in `components/backend` on the same version as `apache-airflow` in `components/dags`.
- Feature flags are declared in `components/lib` (see its AGENTS.md).

## Key libraries

- The QGIS plugin's `qgis` extra conflicts with `dags[airflow]` and `db[shapely]`; sync with `make sync` instead of `uv sync --all-extras`.

## Common pitfalls

1. Unit tests: `make test`. Integration tests (`make test-integration`) and e2e tests need the containers up and migrated (`make up db-migrate-all`). Run QGIS-related tests (`qgis_plugin`, `e2e`) with `--qgis_disable_gui` unless asked otherwise.
2. Commit messages are Conventional Commits, scoped with the component directory name (e.g. `fix(db): ...`); they drive per-component releases.
3. Do not edit `CHANGELOG.md` files, `external/LAStools/` or `.agents/skills/` (see also the db rules on migrations and docs).
4. `.agents/skills/` comes from a Copier template (`.copier-answers.agent-instructions.yml`). If a skill is missing, wrong or should cover something, tell the developer so they can improve the template; never edit local skills.
5. Run `uv run prek run` before finishing; it includes ruff, mypy, sqlfluff, import-linter, license headers and gitlint.

## Agent Skills

- When editing Python files, load `nls-python`.
- When editing SQL files or database migrations, load `nls-sql`.
- When editing Airflow DAGs, tasks or sensors, load `nls-airflow`.
- When editing QGIS plugin code, load `nls-qgis` and `pyqgis-dev`.
- When editing agent instruction files or skills, load `nls-ai-housekeeping`.

Component instructions: [lib](components/lib/AGENTS.md), [db](components/db/AGENTS.md), [processing](components/processing/AGENTS.md), [dags](components/dags/AGENTS.md), [backend](components/backend/AGENTS.md), [qgis_plugin](components/qgis_plugin/AGENTS.md).

## Reference documentation

When working in an area covered by one of these files, read it first: [README](README.md), [dev container](.devcontainer/README.md), and the component READMEs for [lib](components/lib/README.md), [db](components/db/README.md), [processing](components/processing/README.md), [dags](components/dags/README.md), [backend](components/backend/README.md), [qgis_plugin](components/qgis_plugin/README.md) and [e2e](components/e2e/README.md).
