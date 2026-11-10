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

## Settings

- Before reading or writing settings, check whether the plugin already has a settings helper module (for example one from `qgis_plugin_tools` or the plugin's own) and use it instead of calling `QgsSettings` directly. Follow the helper's conventions for key naming, defaults and types. The rules below apply when no helper exists, and to code inside the helper itself.
- Use `QgsSettings` (not `QSettings`) for all user-level QGIS and plugin settings. It wraps `QSettings`, uses the active QGIS profile's settings storage, and falls back to read-only global defaults (`qgis_global_settings.ini`) before the default value.
- Use `QSettings` only for non-QGIS contexts, such as standalone Qt code that does not run inside QGIS or must not use QGIS profile or global-settings handling. Do not use it in plugin code, because it bypasses the profile and global defaults.
- When configuring a third-party plugin through its settings, use whichever of `QSettings` or `QgsSettings` that plugin uses, and only for that integration. Check the plugin's source to find out which.
- Namespace plugin keys with the plugin name, for example `QgsSettings().setValue("myplugin/mykey", value)`, or use `beginGroup()`/`endGroup()`.
- Always pass a default and a `type=` to `value()` (for example `s.value("myplugin/flag", False, type=bool)`), because values from INI storage can return as strings.
- Use `QgsProject.instance().writeEntry()`/`readEntry()` (and typed variants) for project-specific settings, and `layer.setCustomProperty()`/`customProperty()` for layer-specific settings. Both are stored in the project file, not in user settings.
- Prefer `QgsSettingsEntry*` classes (QGIS 3.32+) for typed, documented settings when the plugin's minimum supported QGIS version allows it.

## Styles

- Rendering hangs in waitForFinished(): Cross-layer expressions such as aggregate() can require main-thread execution. Blocking the GUI thread while waiting for a background renderer can deadlock. Keep Qt events processing while awaiting finished; in pytest, connect with qtbot.waitSignal(job.finished, timeout=...) before calling job.start()

## Translation files

- Never directly edit translation files with the `.ts` or `.qm` suffix.
- Update `.ts` files by running `qpdt ts` with the project's virtual environment active; this step may be left to the developer.
- Agents must not attempt to use Qt Linguist. After `.ts` files are updated, leave adding translations and releasing them to update the `.qm` files in Qt Linguist to the developer.

## Testing

- Run QGIS-related tests with pytest-qgis's `--qgis_disable_gui` flag unless the developer explicitly asks for the GUI; a visible window or modal dialog can hang the run.
- If a canvas-dependent test (dock widgets, extent, layer order) fails unexpectedly, try `@pytest.mark.qgis_show_map(timeout=0)`; it is non-blocking and works with `--qgis_disable_gui`.
- Never commit `qgis_show_map` with a non-zero timeout; it opens a blocking map window.
