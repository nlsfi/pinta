<!-- markdownlint-disable MD041 -->
See root AGENTS.md for shared conventions.

# Agent Instructions — processing

Point cloud and raster processing (laspy, rasterio, geopandas, scipy). Runs
as a container image started by Airflow `@task.docker` tasks.

## Structure

- `pipelines.py`, `core.py`: pipeline framework; stages live in `reader/`,
  `filters/` and `writer/`.
- `scripts/`: entry points that DAG tasks import and call inside the
  processing container.

## Rules

- Read the README sections on staging tables, the global tile grid and
  dissolving before changing raster ingestion or update-area logic.
- When changing a `scripts/` function signature, update the calling
  tasks in `components/dags`.
- Dependency changes need a container rebuild (`Containerfile`); native
  build dependencies come from `Containerfile.build-dependecies`.
- LAStools binaries live in `external/LAStools/`; tests run it in demo mode.

## Tests

- Unit: `uv run pytest test_processing`
- Integration (databases up and migrated): `uv run pytest test_integration_processing`
