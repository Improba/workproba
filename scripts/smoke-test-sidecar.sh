#!/usr/bin/env bash
# Smoke-test a built sidecar binary (expects /health on 127.0.0.1:8765).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIPLE="$(bash "$ROOT_DIR/scripts/detect-host-tuple.sh")"
BIN="$ROOT_DIR/desktop/src-tauri/binaries/workproba-ai-${TRIPLE}"

if [[ "${RUNNER_OS:-}" == "Windows" || "$TRIPLE" == *windows* ]]; then
  BIN="${BIN}.exe"
fi

if [[ ! -f "$BIN" ]]; then
  echo "Sidecar binary not found: $BIN" >&2
  echo "Binaries directory:" >&2
  ls -la "$ROOT_DIR/desktop/src-tauri/binaries" 2>&1 >&2 || true
  exit 1
fi

kill_pid() {
  local pid="$1"
  if [[ "${RUNNER_OS:-}" == "Windows" || "$TRIPLE" == *windows* ]]; then
    # Git Bash $! is not always the Win32 PID; best-effort cleanup.
    taskkill //PID "$pid" //F 2>/dev/null || true
    taskkill //IM "workproba-ai-${TRIPLE}.exe" //F 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
}

free_port() {
  local port="${1:-8765}"
  if [[ "${RUNNER_OS:-}" == "Windows" || "$TRIPLE" == *windows* ]]; then
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

LOG="$(mktemp "${TMPDIR:-/tmp}/workproba-sidecar-smoke.XXXXXX")"
"$BIN" >"$LOG" 2>&1 &
PID=$!
trap 'kill_pid "$PID"; rm -f "$LOG"' EXIT

IS_WINDOWS=0
if [[ "${RUNNER_OS:-}" == "Windows" || "$TRIPLE" == *windows* ]]; then
  IS_WINDOWS=1
fi

for _ in $(seq 1 90); do
  if curl -fsS --max-time 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then
    echo "Sidecar healthy ($BIN)"
    exit 0
  fi
  # On Windows/Git Bash, $! is unreliable for Win32 PIDs — do not treat a
  # missing PID as an early crash; wait for health or timeout instead.
  if [[ "$IS_WINDOWS" -eq 0 ]]; then
    if ! kill -0 "$PID" 2>/dev/null; then
      echo "Sidecar process exited before becoming healthy" >&2
      echo "--- sidecar log ---" >&2
      cat "$LOG" >&2 || true
      exit 1
    fi
  fi
  sleep 1
done

echo "Sidecar failed to become healthy within 90s" >&2
echo "--- sidecar log ---" >&2
cat "$LOG" >&2 || true
exit 1
