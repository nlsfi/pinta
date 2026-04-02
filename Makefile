include .env

# Repository directories

# ROOT_DIR is absolute path to the root directory that resolves also in container
# REPO_DIR on the other hand might be something like /mnt/c/... if developing in WSL
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
COMPONENTS_DIR := $(ROOT_DIR)/components
DB_DIR := $(COMPONENTS_DIR)/db
QGIS_DIR := $(COMPONENTS_DIR)/qgis_plugin
DAGS_DIR := $(COMPONENTS_DIR)/dags
E2E_DIR := $(COMPONENTS_DIR)/e2e

# Env variables
export AIRFLOW_HOME := $(DAGS_DIR)/.airflow/
export AIRFLOW_CONN_PINTA_PROCESSING_DB :=postgres://$(PINTA_DB_EDITOR_USER):$(PINTA_DB_EDITOR_PASSWORD)@$(DB_HOST):$(DB_PORT)/$(DB_NAME)
export AIRFLOW__CORE__DAGS_FOLDER := $(DAGS_DIR)/src/pinta_dags/dags
export AIRFLOW__CORE__LOAD_EXAMPLES := false
export AIRFLOW__API__EXPOSE_CONFIG := true


# UV targets
# ==========

sync:
	uv sync --all-packages --all-groups --all-extras --no-extra qgis --no-extra build

sync-all-but-qgis:
	uv sync --all-packages --all-groups --no-group qgis --all-extras --no-extra qgis --no-extra build

# Infra targets
# =================

down:
	docker-compose down -v --remove-orphans

up:
	docker-compose up -d

build:
	docker-compose --profile ansible build

restart-fully: down build up

restart: down up

infra-full:
	docker-compose run --rm ansible

migrations:
	docker-compose run --rm ansible ansible-playbook full.yml -i inventories/local -e skip_db_initialization=1

infra-restart: restart infra-full


# QGIS plugin targets
# =================

qgis-start:
	# Start qgis with plugin in development mode
	uv run --directory $(QGIS_DIR) --extra qgis qpdt s

qgis-start-no-extras:
	# To start QGIS with plugin in development mode without installing qgis extras (works better with native linux development)
	uv run --directory $(QGIS_DIR) qpdt s


# Airflow targets
# ===============

airflow-clean:
	rm -r $(AIRFLOW_HOME)

airflow-migrate:
	uv run --directory $(DAGS_DIR) airflow db migrate

airflow-set-variables:
	uv run --directory $(DAGS_DIR) airflow variables set pinta_processing_task_log_level DEBUG
	uv run --directory $(DAGS_DIR) airflow variables set pinta_processing_code_mount_dir $(REPO_DIR)
	uv run --directory $(DAGS_DIR) airflow variables set pinta_processing_image "localhost/pinta-processing"
	uv run --directory $(DAGS_DIR) airflow variables set pinta_docker_socket_url unix:///var/run/docker.sock

airflow-start: airflow-migrate airflow-set-variables
	uv run --directory $(DAGS_DIR) airflow standalone

airflow-reserialize: airflow-set-variables
	uv run --directory $(DAGS_DIR) airflow dags reserialize

# Tests
# ======

test: sync
	uv run pytest -k "not test_integration" --ignore=$(E2E_DIR)

test-integration: sync-all-but-qgis
	uv run pytest -v -k test_integration --ignore=$(E2E_DIR) --ignore=$(QGIS_DIR)

test-e2e: sync
	uv run --directory $(E2E_DIR) pytest

test-all: test test-integration test-e2e
