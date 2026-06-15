#!/bin/bash

# Applied from https://github.com/postgis/docker-postgis licensed under MIT license

set -euo pipefail

export PGUSER="$POSTGRES_USER"
# DB name
PRIMARY_DB_NAME="pinta"
JOB_DB_NAME="job_template"

# Admin user
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"

# Owner role
OWNER_ROLE="pinta_owner"

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
EOSQL

  check_extension "${db_name}" "postgis"
  check_extension "${db_name}" "postgis_raster"
}

check_extension "${TEMPLATE_NAME}" "postgis"
check_extension "${TEMPLATE_NAME}" "postgis_raster"

echo "Creating admin user and owner role"
psql <<EOSQL
  CREATE ROLE "${ADMIN_USER}" LOGIN CREATEDB CREATEROLE PASSWORD '${ADMIN_PASSWORD}';
  CREATE ROLE "${OWNER_ROLE}" NOLOGIN CREATEROLE;
  GRANT "${OWNER_ROLE}" TO "${ADMIN_USER}";
  GRANT pg_signal_backend TO "${ADMIN_USER}";
EOSQL

create_application_database "${PRIMARY_DB_NAME}"
create_application_database "${JOB_DB_NAME}"

echo "Set ${JOB_DB_NAME} to be a template database"
psql <<EOSQL
  ALTER DATABASE "${JOB_DB_NAME}" IS_TEMPLATE true;
EOSQL

echo "Disabling autovacuum (development/test container only)"
psql <<EOSQL
  ALTER SYSTEM SET autovacuum = off;
  SELECT pg_reload_conf();
EOSQL
