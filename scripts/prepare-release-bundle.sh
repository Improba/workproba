#!/usr/bin/env bash
# Merge per-platform CI artifacts and emit SHA256SUMS.txt for GitHub Release.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$ROOT_DIR/artifacts/release"
DOWNLOAD_ROOT="$ROOT_DIR/artifacts"

rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"

shopt -s nullglob
for dir in "$DOWNLOAD_ROOT"/release-*/; do
  for file in "$dir"/*; do
    [[ -f "$file" ]] || continue
    base="$(basename "$file")"
    if [[ -f "$BUNDLE_DIR/$base" ]]; then
      echo "Warning: duplicate artifact name $base (keeping last)" >&2
    fi
    cp -f "$file" "$BUNDLE_DIR/$base"
  done
done

if [[ -z "$(ls -A "$BUNDLE_DIR")" ]]; then
  echo "Release bundle is empty" >&2
  exit 1
fi

(
  cd "$BUNDLE_DIR"
  sha256sum ./* > SHA256SUMS.txt
)

echo "Release bundle ready: $(find "$BUNDLE_DIR" -maxdepth 1 -type f | wc -l) file(s)"
