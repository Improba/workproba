#!/usr/bin/env bash
# Smoke-test a built sidecar binary (expects /health on 127.0.0.1:8765).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIPLE="$(bash "$ROOT_DIR/scripts/detect-host-tuple.sh")"
BIN="$ROOT_DIR/desktop/src-tauri/binaries/workproba-ai-${TRIPLE}"

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  BIN="${BIN}.exe"
fi

if [[ ! -f "$BIN" ]]; then
  echo "Sidecar binary not found: $BIN" >&2
  exit 1
fi

kill_pid() {
  local pid="$1"
  if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
    taskkill //PID "$pid" //F 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
}

free_port() {
  local port="${1:-8765}"
  if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
    netstat -ano 2>/dev/null | grep ":${port} " | awk '{print $5}' | sort -u | while read -r pid; do
      [[ -n "$pid" && "$pid" != "0" ]] && taskkill //PID "$pid" //F 2>/dev/null || true
    done
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti:"${port}" | xargs -r kill 2>/dev/null || true
  fi
  sleep 0.5
}

free_port 8765

"$BIN" &
PID=$!
trap 'kill_pid "$PID"' EXIT

for _ in $(seq 1 90); do
  if curl -fsS --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
    echo "Sidecar healthy ($BIN)"
    exit 0
  fi
  if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
    tasklist //FI "PID eq $PID" 2>/dev/null | grep -q "$PID" || {
      echo "Sidecar process exited before becoming healthy" >&2
      exit 1
    }
  elif ! kill -0 "$PID" 2>/dev/null; then
    echo "Sidecar process exited before becoming healthy" >&2
    exit 1
  fi
  sleep 1
done

echo "Sidecar failed to become healthy within 90s" >&2
exit 1
