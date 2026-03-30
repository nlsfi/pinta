#!/bin/sh

REPO_ROOT=${REPO_ROOT:-/workspace}

. $REPO_ROOT/.env

# core configurations
export AIRFLOW_HOME=$REPO_ROOT/components/pinta-dags/.airflow
export AIRFLOW__CORE__DAGS_FOLDER=$REPO_ROOT/components/pinta-dags/src/pinta_dags/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=false
export AIRFLOW__API__EXPOSE_CONFIG=true

# configurations
export AIRFLOW__PINTA_PROCESSING__PINTA_PROCESSING_ENV_PYTHON=$REPO_ROOT/components/pinta-processing/.venv/pinta-processing/bin/python

# connections
export AIRFLOW_CONN_PINTA_PROCESSING_DB=postgres://user:password@host:5432/some-db-name

# variables using env vars
export AIRFLOW_VAR_EXAMPLE_VAR=${EXAMPLE_VAR:-notset}

source $REPO_ROOT/components/pinta-dags/.venv/pinta-dags/bin/activate

airflow db migrate

# variables editable from Airflow GUI
airflow variables set pinta_processing_task_log_level DEBUG

airflow standalone
