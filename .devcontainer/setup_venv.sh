#!/bin/bash
set -e

COMPONENTS_DIR="components"


if [ ! -d .venv ]; then
	uv venv --system-site-packages --clear .venv
fi

source .venv/bin/activate
# Cache (most) of the dependencies
uv sync --all-packages --all-groups --all-extras --no-extra qgis --no-extra build
# Keep only the root dependencies initially
uv sync
prek install
