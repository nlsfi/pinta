#!/bin/bash
set -e

COMPONENTS_DIR="components"
LASTOOLS_DIR="external/LAStools"
LASTOOLS_TARBALL_URL="https://raw.githubusercontent.com/LAStools/LAStools.github.io/5bfd81f57975b312b893135f613417acbc698cbe/download/LAStools.tar.gz"


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
# Keep the .tar.gz for local processing container
# build in podman (multi stage build behaves differently on podman than docker)
if [ ! -x "$LASTOOLS_DIR/bin/blast2dem64" ]; then
	echo "Downloading LASTools binaries to $LASTOOLS_DIR..."
	mkdir -p "$LASTOOLS_DIR"
	tarball="$LASTOOLS_DIR/LAStools.tar.gz"
	curl -fsSL "$LASTOOLS_TARBALL_URL" -o "$tarball"
	tar -xzf "$tarball" -C "$LASTOOLS_DIR"
	rm -rf "$LASTOOLS_DIR/data"
fi

# Make completion for `make` targets
cat > ~/.make-targets-completion.bash <<'EOF'
_make_targets() {
  local cur makefile targets
  cur="${COMP_WORDS[COMP_CWORD]}"

  if [[ -f Makefile ]]; then
    makefile="Makefile"
  elif [[ -f makefile ]]; then
    makefile="makefile"
  else
    return 0
  fi

  targets="$(
    grep -E '^[a-zA-Z0-9_.-]+:' "$makefile" \
      | sed 's/:.*//' \
      | sort -u
  )"

  COMPREPLY=($(compgen -W "$targets" -- "$cur"))
}

complete -F _make_targets make
EOF

if ! grep -q "make-targets-completion" ~/.bashrc; then
  cat >> ~/.bashrc <<'EOF'

# Makefile target completion
if [ -f ~/.make-targets-completion.bash ]; then
  . ~/.make-targets-completion.bash
fi
EOF
fi

if ! grep -q "# devcontainer aliases" ~/.bashrc; then
  cat >> ~/.bashrc <<'EOF'

# devcontainer aliases
alias ur='uv run'
alias d='docker'
alias dc='docker compose'
EOF
fi
