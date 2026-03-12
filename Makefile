include .env

# Repository directories
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
COMPONENTS_DIR := $(ROOT_DIR)/components
DB_DIR := $(COMPONENTS_DIR)/db
QGIS_DIR := $(COMPONENTS_DIR)/qgis_plugin

down:
	docker-compose down -v --remove-orphans

up:
	docker-compose up -d

build:
	docker-compose --profile ansible build

restart-fully: down build up

restart: down up

sync:
	uv sync --all-packages --all-groups

# Infra targets
# =================

infra-full:
	docker-compose run --rm ansible

infra-restart: restart ansible-full
