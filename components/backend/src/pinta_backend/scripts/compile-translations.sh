#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="src/pinta_backend"
LOCALE_DIR="$SRC_DIR/locales"
DOMAIN="messages"

echo "Compiling translations..."

for po_file in "$LOCALE_DIR"/*/LC_MESSAGES/"$DOMAIN.po"; do
  [ -e "$po_file" ] || continue

  locale="$(basename "$(dirname "$(dirname "$po_file")")")"
  mo_file="$LOCALE_DIR/$locale/LC_MESSAGES/$DOMAIN.mo"

  echo "Compiling $locale..."

  msgfmt \
    --check \
    --verbose \
    "$po_file" \
    --output-file="$mo_file"
done


echo "Done."
