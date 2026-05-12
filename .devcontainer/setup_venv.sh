#!/bin/bash
set -e

COMPONENTS_DIR="components"
LASTOOLS_DIR="external/LAStools"
LASTOOLS_TARBALL_URL="https://downloads.rapidlasso.de/LAStools.tar.gz"


if [ ! -d .venv ]; then
	uv venv --system-site-packages --clear .venv
fi

source .venv/bin/activate
# Cache (most) of the dependencies
uv sync --all-packages --all-groups --all-extras --no-extra qgis --no-extra build
# Keep only the root dependencies initially
uv sync
prek install

# Download prebuilt LASTools binaries
if [ ! -x "$LASTOOLS_DIR/bin/blast2dem64" ]; then
	echo "Downloading LASTools binaries to $LASTOOLS_DIR..."
	mkdir -p "$LASTOOLS_DIR"
	tarball=$(mktemp --suffix=.tar.gz)
	curl -fsSL "$LASTOOLS_TARBALL_URL" -o "$tarball"
	tar -xzf "$tarball" -C "$LASTOOLS_DIR"
	rm -f "$tarball"
fi
