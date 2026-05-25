#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="src/pinta_backend"
LOCALE_DIR="$SRC_DIR/locales"
DOMAIN="messages"
POT_FILE="$LOCALE_DIR/$DOMAIN.pot"

normalize_po_headers() {
  local file="$1"

  sed -i \
    -e '/^"POT-Creation-Date:/d' \
    -e '/^"PO-Revision-Date:/d' \
    "$file"
}

mkdir -p "$LOCALE_DIR"

echo "Extracting strings..."
find "$SRC_DIR" -name "*.py" -print0 \
  | xargs -0 xgettext \
      --language=Python \
      --keyword=_ \
      --from-code=UTF-8 \
      --sort-output \
      --output="$POT_FILE"

normalize_po_headers "$POT_FILE"

for po_file in "$LOCALE_DIR"/*/LC_MESSAGES/"$DOMAIN.po"; do
  [ -e "$po_file" ] || continue

  locale="$(basename "$(dirname "$(dirname "$po_file")")")"
  mo_file="$LOCALE_DIR/$locale/LC_MESSAGES/$DOMAIN.mo"

  echo "Updating $locale..."

  msgmerge \
    --update \
    --backup=none \
    --sort-output \
    "$po_file" \
    "$POT_FILE"

  normalize_po_headers "$po_file"
done
