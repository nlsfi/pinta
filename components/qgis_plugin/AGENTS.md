<!-- markdownlint-disable MD041 -->
See root AGENTS.md for shared conventions.

# Agent Instructions — qgis_plugin

QGIS plugin for reviewing and approving terrain changes. Licensed GPLv3,
unlike the rest of the repo.

Load `nls-qgis` and `pyqgis-dev` before editing plugin code.

## Rules

- Every `.py` file carries the GPL header from `copyright-header.txt`; the
  MIT header hook is excluded here, so add the GPL header yourself.
- Use psycopg2 (`qgis` extra); do not add psycopg3, Airflow or shapely
  dependencies.
- Wrap user-facing strings in `tr()`; update `.ts` files with
  `qpdt transup` and compile with `qpdt transcompile`.
- Non-Python package data (`*.ui`, `*.svg`, `*.ts`, `resources/`,
  `metadata.txt`) must match the `include` list in `pyproject.toml`.
- Default basemaps: `src/pinta_qgis_plugin/resources/layer_config/basemap_layer_config.json`.

## Run and test

- Start QGIS with the plugin: `make qgis-start` (repo root).
- Tests: `uv run pytest --qgis_disable_gui` from this directory. Always pass
  `--qgis_disable_gui` unless asked otherwise; `make test-qgis` does not.
