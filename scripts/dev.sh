#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
AI_PORT=8765
QUASAR_PORT=5053

PIDS=()

cleanup() {
  echo ""
  echo "Stopping background services..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

START_QUASAR="${START_QUASAR:-0}"
for arg in "$@"; do
  case "$arg" in
    --quasar) START_QUASAR=1 ;;
  esac
done

echo "Starting Python AI sidecar on port ${AI_PORT}..."
cd "$ROOT_DIR/services/ai"
if [[ -x ./run_dev.sh ]]; then
  AI_PORT="$AI_PORT" ./run_dev.sh &
else
  uvicorn app.main:app --host 127.0.0.1 --port "$AI_PORT" --reload &
fi
PIDS+=($!)

if [[ "$START_QUASAR" == "1" ]]; then
  echo "Starting Quasar dev server on port ${QUASAR_PORT}..."
  cd "$ROOT_DIR/front"
  yarn dev &
  PIDS+=($!)
else
  echo "Quasar: skipped (tauri dev starts it via beforeDevCommand)"
fi

echo ""
echo "────────────────────────────────────────"
echo "Next: in another terminal"
echo "  cd desktop && yarn dev"
echo ""
echo "  Python sidecar: http://127.0.0.1:${AI_PORT}"
if [[ "$START_QUASAR" == "1" ]]; then
  echo "  Quasar:         http://localhost:${QUASAR_PORT}"
fi
echo "────────────────────────────────────────"
echo "Press Ctrl+C to stop background services."

wait
