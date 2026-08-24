include .env

# Repository directories

# ROOT_DIR is absolute path to the root directory that resolves also in container
# REPO_DIR on the other hand might be something like /mnt/c/... if developing in WSL
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
COMPONENTS_DIR := $(ROOT_DIR)/components
DB_DIR := $(COMPONENTS_DIR)/db
QGIS_DIR := $(COMPONENTS_DIR)/qgis_plugin
DAGS_DIR := $(COMPONENTS_DIR)/dags
BACKEND_DIR := $(COMPONENTS_DIR)/backend
E2E_DIR := $(COMPONENTS_DIR)/e2e

# Env variables
export AIRFLOW_HOME := $(DAGS_DIR)/.airflow/
export AIRFLOW_CONN_PINTA_PROCESSING_DB :=postgres://$(DB_PRIMARY_PROCESSING_WORKER_USER):$(DB_PRIMARY_PROCESSING_WORKER_PASSWORD)@host.docker.internal:$(DB_PRIMARY_PORT)/$(DB_PRIMARY_NAME)
export AIRFLOW_CONN_PINTA_JOB_DB_ADMIN :=postgres://$(DB_JOB_ADMIN_USER):$(DB_JOB_ADMIN_PASSWORD)@host.docker.internal:$(DB_JOB_PORT)/$(DB_JOB_TEMPLATE_NAME)
export AIRFLOW_CONN_PINTA_JOB_DB :=postgres://$(DB_JOB_PROCESSING_WORKER_USER):$(DB_JOB_PROCESSING_WORKER_PASSWORD)@host.docker.internal:$(DB_JOB_PORT)/$(DB_JOB_TEMPLATE_NAME)
export AIRFLOW__CORE__DAGS_FOLDER := $(DAGS_DIR)/src/pinta_dags/dags
export AIRFLOW__CORE__LOAD_EXAMPLES := false
export AIRFLOW__API__EXPOSE_CONFIG := true
export QGIS_GLOBAL_SETTINGS_FILE := $(QGIS_DIR)/settings.ini

# Backend SimpleAuthManager user that pinta_backend authenticates as.
# Changing the user or its password requires re-running 'make airflow-clean
# airflow-start' so the password file is rewritten.
PINTA_BACKEND_USERNAME ?= pinta-backend
PINTA_BACKEND_AIRFLOW_PASSWORD ?= pinta-backend
AIRFLOW_ADMIN_PASSWORD ?= admin
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS := admin:admin,$(PINTA_BACKEND_USERNAME):op


# UV targets
# ==========

venv:
	UV_PYTHON=/usr/bin/python3 uv venv --system-site-packages --clear

sync:
	uv sync --all-packages --all-groups --all-extras --no-extra qgis --no-extra build

sync-all-but-qgis-and-airflow:
	uv sync --all-packages --all-groups --no-group qgis --no-group airflow --all-extras --no-extra qgis --no-extra build

# Docker Compose targets
# =================

down:
	docker compose down -v --remove-orphans

pull:
	docker compose pull

up:
	# `processing` is an image-only service (no daemon), so we wait on the
	# long-running services explicitly. `up` (no service arg) would still
	# create the processing container, but `--wait` would then fail because
	# it exits immediately.
	docker compose up -d --wait db airflow backend

up-db:
	docker compose up -d --wait db

up-airflow:
	docker compose up -d --wait airflow

up-backend:
	docker compose up -d --wait backend

build:
	docker compose build

build-qgis:
	docker compose build qgis

build-db:
	docker compose build db

build-airflow:
	docker compose build airflow

restart-fully: down pull up


# Database targets
# ================

db-migrate-primary:
	uv run --extra migrations --directory $(DB_DIR) alembic -c migrations/primary/alembic.ini upgrade head

db-migrate-job:
	uv run --extra migrations --directory $(DB_DIR) alembic -c migrations/job/alembic.ini upgrade head

db-migrate-all: db-migrate-primary db-migrate-job db-sync-users

db-sync-users:
	@docker compose exec -T \
	  -e PGPASSWORD=$(DB_PRIMARY_ADMIN_PASSWORD) \
	  db psql \
	  -h localhost \
	  -U $(DB_PRIMARY_ADMIN_USER) -d $(DB_PRIMARY_NAME) \
	  < components/db/scripts/create_development_users.sql

db-restart: restart db-migrate-all

db-restart-fully: down build-db up db-migrate-all

db-build-documentation:
	# Meant to be run by CI for maintaining documentation.
	docker compose run --rm --user $$(id -u):$$(id -g) tbls doc --rm-dist --config .tbls_primary.yml
	docker compose run --rm --user $$(id -u):$$(id -g) tbls doc --rm-dist --config .tbls_job.yml
	uv run --directory $(DB_DIR) scripts/build_diagrams.py

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

AIRFLOW_VERSION ?= 3.3.1
AIRFLOW_PYTHON_VERSION ?= 3.12
AIRFLOW_CONSTRAINTS_DIR := $(DAGS_DIR)/.airflow/constraints
AIRFLOW_MODIFIED_CONSTRAINTS := $(AIRFLOW_CONSTRAINTS_DIR)/constraints-$(AIRFLOW_VERSION)-py$(AIRFLOW_PYTHON_VERSION).txt

AIRFLOW_PASSWORD_FILE := $(AIRFLOW_HOME)simple_auth_manager_passwords.json.generated

airflow-clean:
	rm -r $(AIRFLOW_HOME)

airflow-prepare-constraints:
	uv run --directory $(DAGS_DIR) python -m pinta_dags.scripts.prepare_airflow_constraints \
	  --airflow-version $(AIRFLOW_VERSION) \
	  --python-version $(AIRFLOW_PYTHON_VERSION) \
	  --output $(AIRFLOW_MODIFIED_CONSTRAINTS)

# Pre-write deterministic passwords
airflow-write-passwords:
	@mkdir -p "$(AIRFLOW_HOME)"
	@if [ ! -s "$(AIRFLOW_PASSWORD_FILE)" ]; then \
	  printf '{"admin":"%s","%s":"%s"}\n' \
	    '$(AIRFLOW_ADMIN_PASSWORD)' \
	    '$(PINTA_BACKEND_USERNAME)' \
	    '$(PINTA_BACKEND_AIRFLOW_PASSWORD)' \
	    > "$(AIRFLOW_PASSWORD_FILE)"; \
	fi

airflow-migrate:
	uv run --directory $(DAGS_DIR) --extra airflow airflow db migrate

# Local airflow loads the static vars shared with the container from
# .env.airflow, then sets the host-path variables.
AIRFLOW_LOCAL_ENV = set -a && . $(ROOT_DIR)/.env.airflow && set +a && \
	AIRFLOW_VAR_PINTA_PROCESSING_CODE_MOUNT_DIR=$(REPO_DIR) \
	AIRFLOW_VAR_PINTA_POINT_CLOUD_BASE_PATH=$(ROOT_DIR)/test_data/point_clouds \
	AIRFLOW_VAR_PINTA_CONTAINER_SOURCE_BASE_PATH=$(REPO_DIR)/test_data/point_clouds \
	AIRFLOW_VAR_PINTA_DEM_BASE_PATH=$(REPO_DIR)/test_data/dem \
	AIRFLOW_VAR_PINTA_DATA_BASE_PATH=$(REPO_DIR)/test_data \
	AIRFLOW_VAR_PINTA_PROCESSING_MASK_OGR_SOURCES='{"LAKE_PARTS": "/input/processing/lake_part.gpkg"}' \
	AIRFLOW_VAR_PINTA_LASTOOLS_PATH=$(REPO_DIR)/external/LAStools

airflow-start: airflow-write-passwords airflow-migrate
	$(AIRFLOW_LOCAL_ENV) \
	uv run --directory $(DAGS_DIR) --extra airflow airflow standalone

airflow-reserialize:
	$(AIRFLOW_LOCAL_ENV) \
	uv run --directory $(DAGS_DIR) --extra airflow airflow dags reserialize

# Backend targets
# =================

backend-start:
	@docker compose stop backend || true
	PINTA_BACKEND_AIRFLOW_BASE_URL=$(PINTA_BACKEND_AIRFLOW_BASE_URL) \
	PINTA_BACKEND_AIRFLOW_USERNAME=$(PINTA_BACKEND_AIRFLOW_USERNAME) \
	PINTA_BACKEND_AIRFLOW_PASSWORD=$(PINTA_BACKEND_AIRFLOW_PASSWORD) \
	DB_SRID=$(DB_SRID) \
	DB_PRIMARY_HOST=$(DB_PRIMARY_HOST) \
	DB_PRIMARY_PORT=$(DB_PRIMARY_PORT) \
	DB_PRIMARY_NAME=$(DB_PRIMARY_NAME) \
	DB_PRIMARY_BACKEND_USER=$(DB_PRIMARY_BACKEND_USER) \
	DB_PRIMARY_BACKEND_PASSWORD=$(DB_PRIMARY_BACKEND_PASSWORD) \
	DB_JOB_HOST=$(DB_JOB_HOST) \
	DB_JOB_PORT=$(DB_JOB_PORT) \
	DB_JOB_ADMIN_USER=$(DB_JOB_ADMIN_USER) \
	DB_JOB_ADMIN_PASSWORD=$(DB_JOB_ADMIN_PASSWORD) \
	DB_JOB_TEMPLATE_NAME=$(DB_JOB_TEMPLATE_NAME) \
	DB_DEM_PIXEL_SIZE=$(DB_DEM_PIXEL_SIZE) \
	DB_DEM_NODATA=$(DB_DEM_NODATA) \
	uv run --directory $(BACKEND_DIR) python -m pinta_backend

backend-ts:
	uv run --directory $(BACKEND_DIR) bash ./src/pinta_backend/scripts/update-translations.sh

backend-tc:
	uv run --directory $(BACKEND_DIR) bash ./src/pinta_backend/scripts/compile-translations.sh

# Tests
# ======

COVERAGE_FILE := $(ROOT_DIR)/.coverage
COV_ENV := COVERAGE_FILE=$(COVERAGE_FILE) COVERAGE_PROCESS_START=$(ROOT_DIR)/pyproject.toml


test: sync
	$(COV_ENV) uv run --no-sync coverage run -m pytest -k "not test_integration" --ignore=$(E2E_DIR)

test-integration: sync-all-but-qgis-and-airflow
	$(COV_ENV) uv run --no-sync coverage run -m pytest -v -k test_integration --ignore=$(E2E_DIR) --ignore=$(QGIS_DIR)

test-qgis: sync
	uv run --directory $(QGIS_DIR) pytest -v

# e2e tests run LASTools in demo mode
test-e2e test-e2e-in-container: export AIRFLOW_VAR_PINTA_LASTOOLS_DEMO_MODE := true

test-e2e: sync up db-migrate-all
	uv run --directory $(E2E_DIR) pytest

test-e2e-in-container: up db-migrate-all
	docker compose run --rm qgis uv run --active pytest

test-all: test test-integration test-e2e

coverage-clean:
	rm -f $(ROOT_DIR)/.coverage $(ROOT_DIR)/.coverage.* $(ROOT_DIR)/coverage.xml

coverage-combine:
	uv run --no-sync coverage combine
	uv run --no-sync coverage report
	uv run --no-sync coverage xml
	uv run --no-sync coverage html

# Full local run: unit + integration (needs DB up), then a combined report.
coverage: coverage-clean test test-integration coverage-combine

# PR gate: changed lines (vs origin/main) must stay >= $(COVERAGE_FAIL_UNDER)%
COVERAGE_FAIL_UNDER := 80
COVERAGE_DIFF_MIN_LINES := 20

coverage-diff:
	uvx diff-cover coverage.xml --compare-branch=origin/main \
		--exclude *prepare_airflow_constraints.py \
		--format markdown:diff-cover.md,html:diff-cover.html,json:report.json
	@lines=$$(python3 -c 'import json; print(json.load(open("report.json"))["total_num_lines"])'); \
	pct=$$(python3 -c 'import json; print(json.load(open("report.json"))["total_percent_covered"])'); \
	echo "Changed lines: $$lines, covered: $$pct% (require >= $(COVERAGE_FAIL_UNDER)% above $(COVERAGE_DIFF_MIN_LINES) lines)"; \
	if [ "$$lines" -le $(COVERAGE_DIFF_MIN_LINES) ] || [ "$$pct" -ge $(COVERAGE_FAIL_UNDER) ]; then \
		exit 0; \
	fi; \
	echo "Changed-line coverage $$pct% is below $(COVERAGE_FAIL_UNDER)%. See diff-cover.md or htmlcov/index.html." >&2; \
	exit 1
