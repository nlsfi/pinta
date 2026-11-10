# Geospatial and data pipeline stack

Risks specific to PostGIS, GDAL/OGR, QGIS, OGC services and Airflow. Load this when the detected
stack includes any of them.

## PostGIS, GeoAlchemy2, psycopg

- **Dynamic SQL around spatial functions.** SQL is often
  assembled from configuration or user input: `f"SELECT ST_Area(geom) FROM {table} WHERE {cond}"`.
  Values must be bound parameters; identifiers must come from an allow-list or
  `psycopg.sql.Identifier`; free-form SQL fragments (`WHERE` clauses from config) are injection
  sinks unless the config source is fully trusted and access-controlled. Check who can write that
  config.
- **WKT/WKB/GeoJSON from clients** passed into `ST_GeomFromText('...')` via string formatting.
  Good: `ST_GeomFromText(:wkt, :srid)` with binding, or GeoAlchemy2 functions.
- **Resource exhaustion**: unbounded spatial queries (no bbox limit, no `LIMIT`, no statement
  timeout), very complex geometries (millions of vertices) from clients, `ST_Buffer` with huge
  distances. Look for `statement_timeout` on the role or connection, input size limits.
- **Raster**: `ST_FromGDALRaster` and out-db rasters let PostGIS read files or URLs through GDAL;
  check `postgis.enable_outdb_rasters` and `postgis.gdal_enabled_drivers` are not broadened
  without need.
- **DB privileges**: application role owning schemas, `SUPERUSER`, or able to `CREATE EXTENSION`;
  migrations and runtime using the same role.

## GDAL / OGR / rasterio / fiona / pyogrio

- **Virtual file systems**: GDAL interprets path prefixes such as `/vsicurl/`, `/vsis3/`,
  `/vsizip/`, `/vsitar/`, `/vsigzip/`, `/vsimem/`. A user-supplied path or filename passed to
  `gdal.Open`, `ogr.Open`, `rasterio.open`, `fiona.open` can therefore trigger network requests
  (SSRF) or read local files. Good: never pass raw user strings as paths; build paths yourself
  from validated components; restrict with `GDAL_HTTP_*` settings and
  `CPL_VSIL_CURL_ALLOWED_EXTENSIONS`, or disable network VSI where not needed.
- **Format drivers parse untrusted binary files**; driver bugs have produced memory-safety CVEs.
  Good: restrict drivers explicitly (`allowed_drivers=[...]` in `gdal.OpenEx`, `GDAL_SKIP`),
  keep GDAL current, and process untrusted uploads in an isolated worker.
- **Decompression and size bombs**: zipped shapefiles, GeoPackages, rasters with enormous
  declared dimensions or compression ratios. Check size limits before and after decompression,
  and raster `width * height * bands` limits before reading.
- **Shapefile uploads as zip**: zip slip on extraction (see A01), unexpected extra files.
- **VRT files** (XML) can reference other files and URLs; treat an uploaded `.vrt` like a path
  chosen by the attacker.
- **PROJ network access** (`PROJ_NETWORK=ON`) fetches grids from the network; fine if intended,
  but note it for air-gapped or restricted environments.

## XML formats: GML, WFS/WMS/WMTS capabilities, QML/SLD styles, metadata (ISO 19139)

- Parsed with `lxml` or `xml.etree` → XXE and entity expansion (see A05 in owasp-python.md).
  Use `defusedxml` or a hardened `lxml` parser, especially for content from external services
  or uploads.

## OGC services and proxies

- Server-side proxies that forward WMS/WFS requests to a URL given in a parameter: classic SSRF.
  Allow-list upstream services.
- WFS-T (transactional) endpoints: verify authorisation per feature type and operation.
- CQL/OGC filter expressions passed through to SQL backends: check how the server translates
  them and whether raw SQL can be smuggled.

## QGIS (PyQGIS plugins and project files)

- **Project files can contain Python**: macros (`openProject`/`saveProject` macros) and custom
  expression functions run when a project is opened, subject to QGIS's macro setting. A plugin
  that opens projects from untrusted locations programmatically, or that lowers the macro
  setting, is a code execution risk.
- `QgsExpression` built by concatenating user input: expressions can call functions with side
  effects; build expressions with `QgsExpression.quotedValue`/`quotedColumnRef`.
- Plugins using `eval`/`exec` on layer attributes or settings, or `subprocess` with paths from
  layers.
- Credentials: use `QgsAuthManager`, not plain text in `QgsSettings`, project files or plugin
  config. Check committed `.qgs`/`.qgz` files for embedded connection strings with passwords.
- Plugins downloading and executing code or updating themselves outside the plugin repository.
- HTTP requests made with `QgsNetworkAccessManager` vs `requests`: the latter bypasses QGIS proxy
  and SSL settings; mostly a configuration concern, sometimes a TLS-verification one.

## Airflow DAGs

- **Templated commands**: `BashOperator(bash_command="... {{ dag_run.conf['x'] }} ...")` or
  `{{ params.x }}` is command injection if anyone who can trigger DAGs with config is less
  trusted than the worker. Good: pass values via `env=` and quote them in the script, or use
  PythonOperator/TaskFlow with validated inputs.
- SQL operators with Jinja-templated SQL from `dag_run.conf`: SQL injection.
- `enable_xcom_pickling = True` (pickle deserialisation of XComs).
- Connections and variables: secrets in DAG code or in `Variable.get` defaults; prefer a secrets
  backend. Check that rendered templates and logs do not print secrets.
- Code at DAG module level runs in the scheduler on every parse: network calls or heavy work there
  is both a reliability and an attack-surface issue.
- `default_args` / connections with TLS verification disabled.
