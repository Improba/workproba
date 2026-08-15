#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

HOST="${HOST:-${AI_HOST:-127.0.0.1}}"
PORT="${PORT:-${AI_PORT:-8765}}"

if [[ -d .venv ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

BUNDLED="$SCRIPT_DIR/../../desktop/src-tauri/resources/ms-playwright"
chromium_tree=
if [[ -d "$BUNDLED" ]]; then
  for child in "$BUNDLED"/chromium-[0-9]*; do
    if [[ -d "$child" ]]; then
      chromium_tree=1
      break
    fi
  done
fi
if [[ -n "$chromium_tree" ]]; then
  export PLAYWRIGHT_BROWSERS_PATH="$(cd "$BUNDLED" && pwd)"
  export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
fi

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
