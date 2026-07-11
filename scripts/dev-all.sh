#!/bin/bash
# Lance Workproba en développement : sidecar Python IA + coque Tauri (qui démarre Quasar).
# Usage:
#   bash scripts/dev-all.sh              # tout (sidecar + desktop)
#   bash scripts/dev-all.sh --ai-only    # sidecar Python uniquement
#   bash scripts/dev-all.sh --no-ai      # desktop uniquement (sidecar déjà lancé ailleurs)
#
# Variables d'environnement utiles:
#   AI_PORT       port du sidecar Python (défaut 8765)
#   AI_HOST       host du sidecar       (défaut 127.0.0.1)
#   AI_SKIP_WAIT  =1 pour ne pas attendre la santé du sidecar (démarrage plus rapide)
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
AI_DIR="$ROOT_DIR/services/ai"
DESKTOP_DIR="$ROOT_DIR/desktop"

AI_HOST="${AI_HOST:-127.0.0.1}"
AI_PORT="${AI_PORT:-8765}"
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-30}"
HEALTH_POLL_INTERVAL_S="${HEALTH_POLL_INTERVAL_S:-0.5}"

# Couleurs (réutilise scripts/colors.sh si présent, sinon fallback minimal)
if [[ -f "$SCRIPT_DIR/colors.sh" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/colors.sh"
fi
BLUE="${BLUE:-\033[0;34m}"
GREEN="${GREEN:-\033[0;32m}"
YELLOW="${YELLOW:-\033[0;33m}"
RED="${RED:-\033[0;31m}"
NC="${NC:-\033[0m}"

log()  { printf "${BLUE}▸ %s${NC}\n" "$*"; }
ok()   { printf "${GREEN}✓ %s${NC}\n" "$*"; }
warn() { printf "${YELLOW}⚠ %s${NC}\n" "$*"; }
err()  { printf "${RED}✗ %s${NC}\n" "$*" >&2; }

# ── Args ─────────────────────────────────────────────────────────────────────
AI_ONLY=0
SKIP_AI=0
for arg in "$@"; do
  case "$arg" in
    --ai-only)    AI_ONLY=1 ;;
    --no-ai)      SKIP_AI=1 ;;
    -h|--help)
      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) err "Argument inconnu: $arg"; exit 2 ;;
  esac
done

# ── Pré-vérifications ────────────────────────────────────────────────────────
require() {
  command -v "$1" >/dev/null 2>&1 || { err "Commande requise introuvable: $1"; exit 1; }
}
require bash
require curl  # utilisé pour le probe /health

if [[ $AI_ONLY -eq 0 ]]; then
  command -v cargo >/dev/null 2>&1 || { err "cargo (Rust) est requis pour le desktop. Voir desktop/README.md."; exit 1; }
  command -v yarn >/dev/null 2>&1  || { err "yarn est requis pour le front. Voir README.md."; exit 1; }
  [[ -d "$DESKTOP_DIR/src-tauri" ]] || { err "Dossier desktop/src-tauri introuvable: $DESKTOP_DIR/src-tauri"; exit 1; }
fi
[[ -d "$AI_DIR/app" ]] || { err "Dossier services/ai/app introuvable: $AI_DIR/app"; exit 1; }

# ── État global ──────────────────────────────────────────────────────────────
AI_PID=""
AI_STARTED_BY_US=0
DESKTOP_PID=""
CLEANUP_DONE=0

cleanup() {
  [[ $CLEANUP_DONE -eq 1 ]] && return 0
  CLEANUP_DONE=1
  echo ""
  log "Arrêt des services en cours..."
  # Desktop d'abord (le foreground principal) — tauri dev propage le signal à Quasar
  if [[ -n "${DESKTOP_PID:-}" ]] && kill -0 "$DESKTOP_PID" 2>/dev/null; then
    kill "$DESKTOP_PID" 2>/dev/null || true
    # Laisser tauri dev nettoyer Quasar lui-même
    for _ in 1 2 3 4 5; do
      kill -0 "$DESKTOP_PID" 2>/dev/null || break
      sleep 0.3
    done
    kill -0 "$DESKTOP_PID" 2>/dev/null && kill -TERM "$DESKTOP_PID" 2>/dev/null || true
  fi
  # Sidecar : ne tuer QUE si on l'a démarré nous-même
  if [[ $AI_STARTED_BY_US -eq 1 && -n "${AI_PID:-}" ]] && kill -0 "$AI_PID" 2>/dev/null; then
    log "Arrêt du sidecar Python (PID $AI_PID)..."
    # Tuer le groupe de processus pour emporter uvicorn --reload et ses enfants
    kill -TERM "-$AI_PID" 2>/dev/null || kill -TERM "$AI_PID" 2>/dev/null || true
    for _ in 1 2 3 4 5 6; do
      kill -0 "$AI_PID" 2>/dev/null || break
      sleep 0.3
    done
    kill -0 "$AI_PID" 2>/dev/null && kill -KILL "$AI_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  ok "Terminé."
}
trap cleanup EXIT INT TERM

# ── Probe santé sidecar ──────────────────────────────────────────────────────
# Renvoie 0 si /health répond, 1 sinon. Utilise curl (déjà requis).
probe_health() {
  local url="http://${AI_HOST}:${AI_PORT}/health"
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

# Renvoie 0 si un listener occupe le port (probabilité sidecar déjà lancé).
probe_port() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :${AI_PORT}" 2>/dev/null | grep -q ":${AI_PORT}"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${AI_PORT}" -sTCP:LISTEN -P -n 2>/dev/null | grep -q LISTEN
  else
    # Repli : tentative de connexion TCP via bash
    (echo > "/dev/tcp/${AI_HOST}/${AI_PORT}") 2>/dev/null
  fi
}

# ── Démarrage sidecar ────────────────────────────────────────────────────────
start_sidecar() {
  if [[ $SKIP_AI -eq 1 ]]; then
    warn "Sidecar Python : --no-ai demandé, on suppose qu'il tourne ailleurs."
    return 0
  fi

  if probe_health; then
    ok "Sidecar Python déjà en ligne sur http://${AI_HOST}:${AI_PORT}/health — réutilisé."
    AI_STARTED_BY_US=0
    return 0
  fi
  if probe_port && ! probe_health; then
    warn "Le port ${AI_PORT} est occupé mais /health ne répond pas. Démarrage quand même d'une nouvelle instance possible — vérifiez vos processus."
  fi

  log "Démarrage du sidecar Python sur http://${AI_HOST}:${AI_PORT} ..."
  cd "$AI_DIR"
  AI_HOST="$AI_HOST" AI_PORT="$AI_PORT" ./run_dev.sh >"$ROOT_DIR/.dev-ai.log" 2>&1 &
  AI_PID=$!
  cd "$ROOT_DIR"
  AI_STARTED_BY_US=1

  if [[ "${AI_SKIP_WAIT:-0}" == "1" ]]; then
    warn "AI_SKIP_WAIT=1 — on n'attend pas /health. Logs: tail -f $ROOT_DIR/.dev-ai.log"
    return 0
  fi

  log "Attente de la santé du sidecar (timeout ${HEALTH_TIMEOUT_S}s)..."
  local max_iters=$(( HEALTH_TIMEOUT_S * 2 ))   # 0.5s par itération
  local i=0
  while ! probe_health; do
    if ! kill -0 "$AI_PID" 2>/dev/null; then
      err "Le sidecar Python s'est arrêté prématurément. Logs:"
      tail -n 40 "$ROOT_DIR/.dev-ai.log" 2>/dev/null || true
      exit 1
    fi
    if (( i >= max_iters )); then
      err "Timeout: /health ne répond pas après ${HEALTH_TIMEOUT_S}s. Logs:"
      tail -n 40 "$ROOT_DIR/.dev-ai.log" 2>/dev/null || true
      exit 1
    fi
    sleep "$HEALTH_POLL_INTERVAL_S"
    i=$(( i + 1 ))
  done
  ok "Sidecar Python prêt (PID $AI_PID). Logs: tail -f $ROOT_DIR/.dev-ai.log"
}

# ── Démarrage desktop ────────────────────────────────────────────────────────
start_desktop() {
  if [[ $AI_ONLY -eq 1 ]]; then
    log "Mode --ai-only : desktop non démarré. Ctrl+C pour arrêter le sidecar."
    # Maintient le script vivant : attend le sidecar
    wait "$AI_PID" 2>/dev/null || true
    return 0
  fi

  log "Démarrage du desktop Tauri (Quasar sur port 5053)..."
  (
    cd "$DESKTOP_DIR"
    yarn dev
  ) &
  DESKTOP_PID=$!

  echo ""
  echo "──────────────────────────────────────────────────────────────"
  ok "Workproba en cours d'exécution"
  echo "  Sidecar Python : http://${AI_HOST}:${AI_PORT}/health"
  echo "  Quasar dev     : http://localhost:5053"
  echo "  Logs sidecar   : tail -f $ROOT_DIR/.dev-ai.log"
  echo "  Arrêt          : Ctrl+C (les deux services sont nettoyés)"
  echo "──────────────────────────────────────────────────────────────"
  echo ""

  # Tauri dev au premier plan effectif : on attend le desktop
  wait "$DESKTOP_PID" 2>/dev/null || true
}

start_sidecar
start_desktop
