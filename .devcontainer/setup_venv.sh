#!/bin/bash
set -e

COMPONENTS_DIR="components"

uv venv --system-site-packages --clear
source .venv/bin/activate
uv sync --all-packages --all-groups --all-extras
prek install
