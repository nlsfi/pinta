#!/usr/bin/env bash
# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

set -euo pipefail

# Pre-write deterministic passwords. Airflow only
# regenerates entries that are missing from this file.
if [ -n "${AIRFLOW_SIMPLE_AUTH_MANAGER_PASSWORDS:-}" ]; then
    passwords_file="${AIRFLOW_HOME}/simple_auth_manager_passwords.json.generated"
    mkdir -p "${AIRFLOW_HOME}"
    if [ ! -s "${passwords_file}" ]; then
        printf '%s\n' "${AIRFLOW_SIMPLE_AUTH_MANAGER_PASSWORDS}" > "${passwords_file}"
    fi
fi

# Seed the postgres connections in Airflow's DB (not as AIRFLOW_CONN_* env
# vars) so e2e tests can PATCH them per-test to point at a per-worker
# database clone
airflow db migrate >/dev/null

seed_connection() {
    local conn_id="$1"
    local conn_uri="$2"
    if [ -z "${conn_uri}" ]; then
        return
    fi
    airflow connections delete "${conn_id}" >/dev/null 2>&1 || true
    airflow connections add "${conn_id}" --conn-uri "${conn_uri}" >/dev/null
}

seed_connection "pinta_processing_db" "${AIRFLOW_SEED_CONN_PINTA_PROCESSING_DB:-}"
seed_connection "pinta_job_db_admin" "${AIRFLOW_SEED_CONN_PINTA_JOB_DB_ADMIN:-}"
seed_connection "pinta_job_db" "${AIRFLOW_SEED_CONN_PINTA_JOB_DB:-}"

exec airflow "$@"
