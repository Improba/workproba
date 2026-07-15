#!/usr/bin/env bash
# Collect Tauri bundle outputs for CI artifact upload (one platform per call).
# Portable Bash 3.2+ (macOS runners) — no mapfile.
set -euo pipefail

PLATFORM="${1:?platform label required}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/artifacts/release-${PLATFORM}"
TARGET_ROOT="$ROOT_DIR/desktop/src-tauri/target"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

INSTALLERS=()
while IFS= read -r file; do
  [[ -n "$file" ]] && INSTALLERS+=("$file")
done < <(
  find "$TARGET_ROOT" -type f \( \
    -path '*/release/bundle/dmg/*.dmg' \
    -o -path '*/release/bundle/deb/*.deb' \
    -o -path '*/release/bundle/appimage/*.AppImage' \
    -o -path '*/release/bundle/msi/*.msi' \
    -o -path '*/release/bundle/nsis/*-setup.exe' \
  \) 2>/dev/null | sort
)

if [[ "${#INSTALLERS[@]}" -eq 0 ]]; then
  echo "No installer artifacts found under $TARGET_ROOT" >&2
  echo "Bundle tree (sample):" >&2
  find "$TARGET_ROOT" -path '*/bundle/*' -type f 2>/dev/null | head -30 >&2 || true
  exit 1
fi

for file in "${INSTALLERS[@]}"; do
  cp -f "$file" "$OUT_DIR/"
  echo "Staged: $(basename "$file")"
done

echo "Staged ${#INSTALLERS[@]} installer(s) in $OUT_DIR"
