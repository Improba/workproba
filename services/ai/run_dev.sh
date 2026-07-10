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

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
