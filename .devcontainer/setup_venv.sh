#!/bin/bash
set -e

COMPONENTS_DIR="components"

uv venv --system-site-packages --clear
source .venv/bin/activate
# Cache (most) of the dependencies
uv sync --all-packages --all-groups --all-extras --no-extra qgis
# Keep only the root dependencies initially
uv sync
prek install
