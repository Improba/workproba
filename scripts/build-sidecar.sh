#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DIR="$ROOT_DIR/services/ai"
DEST_DIR="$ROOT_DIR/desktop/src-tauri/binaries"
TRIPLE="$(bash "$ROOT_DIR/scripts/detect-host-tuple.sh")"
EXE_BASENAME="workproba-ai"

mkdir -p "$DEST_DIR"

cd "$AI_DIR"

if [[ -n "${CI:-}" ]]; then
  python -m pip install --upgrade pip
  pip install -e ".[build]"
else
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install -e ".[build]"
fi

rm -rf build dist

pyinstaller workproba_ai.spec --noconfirm

if [[ "$TRIPLE" == *windows* ]]; then
  SRC="dist/${EXE_BASENAME}.exe"
  OUTPUT="$DEST_DIR/${EXE_BASENAME}-${TRIPLE}.exe"
else
  SRC="dist/$EXE_BASENAME"
  OUTPUT="$DEST_DIR/${EXE_BASENAME}-${TRIPLE}"
fi

if [[ ! -f "$SRC" ]]; then
  echo "PyInstaller output missing: $SRC" >&2
  exit 1
fi

rm -f "$OUTPUT"
cp "$SRC" "$OUTPUT"
chmod +x "$OUTPUT"

rm -rf "$DEST_DIR/_internal"

echo "Sidecar built: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
