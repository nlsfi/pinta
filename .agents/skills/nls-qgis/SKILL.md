---
name: nls-qgis
description: NLS QGIS plugin and PyQGIS conventions for resource cleanup, CRS handling, feature editing, processing workflows, and translation files.
---

## Resource cleanup  <!-- markdownlint-disable-line MD041 -->

- Release GDAL datasets explicitly (`dataset = None`) when processing completes.

## CRS handling

- Validate CRS with `layer.crs().isValid()` and inspect `layer.crs().authid()` before spatial logic.
- Do not assume project CRS and layer CRS are the same, even when rendering looks correct.
- Pass explicit CRS and transform context when writing new vector outputs.

## Feature access and editing

- Use `QgsFeatureRequest` to limit attributes, geometry, and feature subsets early.
- Always check the `commitChanges()` return value when committing edits.
- Call `updateFields()` after schema changes and `updateExtents()` after geometry inserts.

## Processing and plugin workflow

- Prefer QGIS Processing algorithms over shelling out or reimplementing core geoprocessing.
- Keep plugin teardown explicit: stop timers and disconnect signals in `deactivate()`.
- If plugin reload causes duplicate handlers, check for missing disconnects before deeper refactors.

## Translation files

- Never directly edit translation files with the `.ts` or `.qm` suffix.
- Update `.ts` files by running `qpdt ts` with the project's virtual environment active; this step may be left to the developer.
- Agents must not attempt to use Qt Linguist. After `.ts` files are updated, leave adding translations and releasing them to update the `.qm` files in Qt Linguist to the developer.

## Testing

- Run QGIS-related tests with pytest-qgis's `--qgis_disable_gui` flag unless the developer explicitly asks for the GUI; a visible window or modal dialog can hang the run.
- If a canvas-dependent test (dock widgets, extent, layer order) fails unexpectedly, try `@pytest.mark.qgis_show_map(timeout=0)`; it is non-blocking and works with `--qgis_disable_gui`.
- Never commit `qgis_show_map` with a non-zero timeout; it opens a blocking map window.
