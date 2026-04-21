#!/bin/bash

# Applied from https://github.com/postgis/docker-postgis licensed under MIT license

set -euo pipefail

export PGUSER="$POSTGRES_USER"

# Admin user
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"

# Roles
OWNER_ROLE="pinta_owner"
READER_ROLE="pinta_reader"
WRITER_ROLE="pinta_writer"
PROCESSING_WORKER_ROLE="pinta_processing_worker"

# Users
QGIS_EDITOR_USER="qgis_editor"
QGIS_EDITOR_PASSWORD="qgis"
QGIS_VIEWER_USER="qgis_viewer"
QGIS_VIEWER_PASSWORD="qgis"
PROCESSING_WORKER_USER="processing_worker"
PROCESSING_WORKER_PASSWORD="processing_worker"

TEMPLATE_NAME="template_postgis"

check_extension() {
  local db="$1"
  local ext="$2"
  local found
  found=$(psql --dbname="${db}" -tAc "SELECT 1 FROM pg_extension WHERE extname = '${ext}'")
  if [ "${found}" != "1" ]; then
    echo "ERROR: extension '${ext}' missing from database '${db}'" >&2
    exit 1
  fi
}

create_application_database() {
  local db_name="$1"

  echo "Creating database ${db_name}"
  psql <<EOSQL
    CREATE DATABASE "${db_name}" OWNER "${OWNER_ROLE}" TEMPLATE "${TEMPLATE_NAME}";
    REVOKE ALL ON DATABASE "${db_name}" FROM PUBLIC;
    GRANT CONNECT, TEMP ON DATABASE "${db_name}" TO "${READER_ROLE}";
    GRANT CONNECT, TEMP ON DATABASE "${db_name}" TO "${WRITER_ROLE}";
    GRANT CONNECT, TEMP ON DATABASE "${db_name}" TO "${PROCESSING_WORKER_ROLE}";
    REVOKE CREATE ON DATABASE "${db_name}" FROM "${READER_ROLE}";
    REVOKE CREATE ON DATABASE "${db_name}" FROM "${WRITER_ROLE}";
    REVOKE CREATE ON DATABASE "${db_name}" FROM "${PROCESSING_WORKER_ROLE}";
EOSQL

  check_extension "${db_name}" "postgis"
  check_extension "${db_name}" "postgis_raster"
}

echo "Creating admin user"
psql <<EOSQL
  CREATE ROLE "${ADMIN_USER}" LOGIN CREATEDB CREATEROLE PASSWORD '${ADMIN_PASSWORD}';
EOSQL

check_extension "${TEMPLATE_NAME}" "postgis"
check_extension "${TEMPLATE_NAME}" "postgis_raster"

echo "Creating application roles and users"
psql <<EOSQL
  CREATE ROLE "${OWNER_ROLE}" NOLOGIN;
  CREATE ROLE "${READER_ROLE}" NOLOGIN;
  CREATE ROLE "${WRITER_ROLE}" NOLOGIN;
  CREATE ROLE "${PROCESSING_WORKER_ROLE}" NOLOGIN;

  CREATE ROLE "${QGIS_EDITOR_USER}" LOGIN PASSWORD '${QGIS_EDITOR_PASSWORD}';
  CREATE ROLE "${QGIS_VIEWER_USER}" LOGIN PASSWORD '${QGIS_VIEWER_PASSWORD}';
  CREATE ROLE "${PROCESSING_WORKER_USER}" LOGIN PASSWORD '${PROCESSING_WORKER_PASSWORD}';

  GRANT "${READER_ROLE}" TO "${WRITER_ROLE}";
  GRANT "${READER_ROLE}" TO "${PROCESSING_WORKER_ROLE}";
  GRANT "${WRITER_ROLE}" TO "${QGIS_EDITOR_USER}";
  GRANT "${READER_ROLE}" TO "${QGIS_VIEWER_USER}";
  GRANT "${PROCESSING_WORKER_ROLE}" TO "${PROCESSING_WORKER_USER}";

  -- Admin needs membership in every application role so it can
  -- ALTER DEFAULT PRIVILEGES on their behalf during schema setup.
  GRANT "${OWNER_ROLE}" TO "${ADMIN_USER}";
  GRANT "${READER_ROLE}" TO "${ADMIN_USER}";
  GRANT "${WRITER_ROLE}" TO "${ADMIN_USER}";
  GRANT "${PROCESSING_WORKER_ROLE}" TO "${ADMIN_USER}";
EOSQL

create_application_database "${MAIN_DB_NAME}"
create_application_database "${JOB_DB_NAME}"

echo "Set ${JOB_DB_NAME} to be a template database"
psql <<EOSQL
  ALTER DATABASE "${JOB_DB_NAME}" IS_TEMPLATE true;
EOSQL
