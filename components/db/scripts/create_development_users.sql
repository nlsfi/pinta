\set ON_ERROR_STOP on

SET ROLE pinta_owner;

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qgis_editor') AS create_editor \gset
\if :create_editor
  CREATE ROLE "qgis_editor" LOGIN PASSWORD 'qgis';
\endif

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qgis_viewer') AS create_viewer \gset
\if :create_viewer
  CREATE ROLE "qgis_viewer" LOGIN PASSWORD 'qgis';
\endif

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'processing_worker') AS create_pw \gset
\if :create_pw
  CREATE ROLE "processing_worker" LOGIN PASSWORD 'processing_worker';
\endif

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'backend_user') AS create_backend \gset
\if :create_backend
  CREATE ROLE "backend_user" LOGIN PASSWORD 'backend_user';
\endif

GRANT "pinta_writer" TO "qgis_editor";
GRANT "pinta_reader" TO "qgis_viewer";
GRANT "pinta_processing_worker" TO "processing_worker";
GRANT "pinta_backend" TO "backend_user";

RESET ROLE;
