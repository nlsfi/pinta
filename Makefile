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
export AIRFLOW_CONN_PINTA_PROCESSING_DB_CONTAINER :=postgres://$(DB_PROCESSING_WORKER_USER):$(DB_PROCESSING_WORKER_PASSWORD)@host.docker.internal:$(DB_PORT)/$(DB_NAME)
export AIRFLOW__CORE__DAGS_FOLDER := $(DAGS_DIR)/src/pinta_dags/dags
export AIRFLOW__CORE__LOAD_EXAMPLES := false
export AIRFLOW__API__EXPOSE_CONFIG := true


# UV targets
# ==========

venv:
	UV_PYTHON=/usr/bin/python3 uv venv --system-site-packages --clear

sync:
	uv sync --all-packages --all-groups --all-extras --no-extra qgis --no-extra build

sync-all-but-qgis-and-airflow:
	uv sync --all-packages --all-groups --no-group qgis --no-group airflow --all-extras --no-extra qgis --no-extra build

# Infra targets
# =================

down:
	docker compose down -v --remove-orphans

up:
	docker compose up -d

build:
	docker compose --profile ansible build

build-qgis:
	docker compose build qgis

restart-fully: down build up

restart: down up

infra-full:
	docker compose run --rm ansible

migrations:
	docker compose run --rm ansible ansible-playbook full.yml -i inventories/local -e skip_db_initialization=1

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
	uv run --directory $(DAGS_DIR) airflow variables set pinta_processing_image "ghcr.io/nlsfi/pinta/processing:latest"
	uv run --directory $(DAGS_DIR) airflow variables set pinta_docker_socket_url unix:///var/run/docker.sock
	uv run --directory $(DAGS_DIR) airflow variables set pinta_point_cloud_base_path $(ROOT_DIR)/test_data/point_clouds
	uv run --directory $(DAGS_DIR) airflow variables set pinta_container_source_base_path $(REPO_DIR)/test_data/point_clouds
	uv run --directory $(DAGS_DIR) airflow variables set pinta_container_target_base_path /data
	uv run --directory $(DAGS_DIR) airflow variables set pinta_db_srid 3067
	uv run --directory $(DAGS_DIR) airflow variables set pinta_db_dem_pixel_size 2
	uv run --directory $(DAGS_DIR) airflow variables set pinta_db_dem_nodata -9999

airflow-start: airflow-migrate airflow-set-variables
	uv run --directory $(DAGS_DIR) airflow standalone

airflow-reserialize: airflow-set-variables
	uv run --directory $(DAGS_DIR) airflow dags reserialize

# Tests
# ======

test: sync
	uv run pytest -k "not test_integration" --ignore=$(E2E_DIR)

test-integration: sync-all-but-qgis-and-airflow
	uv run pytest -v -k test_integration --ignore=$(E2E_DIR) --ignore=$(QGIS_DIR)

test-qgis: sync
	uv run --directory $(QGIS_DIR) pytest -v

test-e2e: sync
	uv run --directory $(E2E_DIR) pytest

test-e2e-in-container:
	docker compose run --rm qgis uv run --active pytest

test-all: test test-integration test-e2e
