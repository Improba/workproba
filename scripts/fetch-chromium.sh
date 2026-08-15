#!/usr/bin/env bash
# Télécharge le Chromium Playwright de la plateforme courante dans les
# resources Tauri (non versionné). À lancer avant `tauri build`.
#
# La contrainte pip (playwright==…) doit rester identique à
# services/ai/pyproject.toml : le driver gelé et le binaire Chromium
# doivent être la même révision.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DIR="$ROOT_DIR/services/ai"
DEST="$ROOT_DIR/desktop/src-tauri/resources/ms-playwright"
MARKER="$DEST/.workproba-chromium"
PYPROJECT="$AI_DIR/pyproject.toml"

log() { printf 'fetch-chromium: %s\n' "$*"; }

has_chromium_tree() {
  local dir="$1"
  [[ -d "$dir" ]] || return 1
  local child
  # Uniquement le Chromium complet (channel=chromium). Le headless-shell ne suffit pas.
  for child in "$dir"/chromium-[0-9]*; do
    [[ -d "$child" ]] || continue
    return 0
  done
  return 1
}

playwright_spec_from_pyproject() {
  "$PYTHON" -c "
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
match = re.search(r'\"(playwright[=<>!~][^\"]+)\"', text)
if not match:
    raise SystemExit('playwright spec introuvable dans pyproject.toml')
print(match.group(1))
" "$PYPROJECT"
}

playwright_version() {
  "$PYTHON" -c "from importlib.metadata import version; print(version('playwright'))"
}

ensure_chromium_exec_bits() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  find "$dir" -type f \( \
    -name chrome -o -name chrome.exe -o -name Chromium \
    -o -name 'Google Chrome for Testing' \
    -o -name chrome-headless-shell -o -name chrome-headless-shell.exe \
    -o -name headless_shell -o -name headless_shell.exe \
    -o -name chrome_crashpad_handler -o -name '*Helper*' \
  \) -exec chmod +x {} + 2>/dev/null || true
}

if [[ -n "${CI:-}" ]]; then
  PYTHON="${PYTHON:-python}"
else
  if [[ -x "$AI_DIR/.venv/bin/python" ]]; then
    PYTHON="$AI_DIR/.venv/bin/python"
  elif [[ -x "$AI_DIR/.venv/Scripts/python.exe" ]]; then
    PYTHON="$AI_DIR/.venv/Scripts/python.exe"
  else
    log "venv services/ai/.venv introuvable. Lancez make build-sidecar ou python -m venv." >&2
    exit 1
  fi
fi

log "Python: $PYTHON"
PW_SPEC="$(playwright_spec_from_pyproject)"
CURRENT_PW=""
if "$PYTHON" -c "import playwright" >/dev/null 2>&1; then
  CURRENT_PW="$(playwright_version)"
fi
EXPECTED_PW=""
if [[ "$PW_SPEC" == playwright==* ]]; then
  EXPECTED_PW="${PW_SPEC#playwright==}"
fi
if [[ -z "$CURRENT_PW" || ( -n "$EXPECTED_PW" && "$CURRENT_PW" != "$EXPECTED_PW" ) ]]; then
  log "alignement $PW_SPEC (actuel=${CURRENT_PW:-absent})"
  "$PYTHON" -m pip install -q "$PW_SPEC"
  CURRENT_PW="$(playwright_version)"
else
  log "playwright déjà aligné ($CURRENT_PW)"
fi
MARKED_PW=""
if [[ -f "$MARKER" ]]; then
  MARKED_PW="$(sed -n 's/^playwright=//p' "$MARKER" | head -n 1 | tr -d '\r')"
fi

if [[ -z "${FORCE:-}" ]] && has_chromium_tree "$DEST" && [[ "$MARKED_PW" == "$CURRENT_PW" ]]; then
  log "déjà présent (playwright=$CURRENT_PW)"
  ensure_chromium_exec_bits "$DEST"
  exit 0
fi

if has_chromium_tree "$DEST" && [[ "$MARKED_PW" != "$CURRENT_PW" ]]; then
  log "arbre présent mais Playwright différent (marker=${MARKED_PW:-absent} actuel=$CURRENT_PW), retéléchargement"
fi

mkdir -p "$DEST"
# Vider les builds navigateur, garder/recréer .gitkeep (dossier versionné).
find "$DEST" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +
touch "$DEST/.gitkeep"
BROWSERS_PATH="$DEST"
if command -v cygpath >/dev/null 2>&1; then
  BROWSERS_PATH="$(cygpath -w "$DEST")"
fi
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_PATH"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# --no-shell : Chromium complet. Le sidecar lance channel=chromium (pas le shell).
set +e
"$PYTHON" -m playwright install chromium --no-shell
install_status=$?
set -e
if [[ "$install_status" -ne 0 ]]; then
  log "--no-shell indisponible, repli: playwright install chromium"
  "$PYTHON" -m playwright install chromium
fi

if ! has_chromium_tree "$DEST"; then
  log "échec: aucun dossier chromium-* dans $DEST" >&2
  ls -la "$DEST" >&2 || true
  exit 1
fi

ensure_chromium_exec_bits "$DEST"

{
  echo "playwright=$CURRENT_PW"
  echo "platform=$(uname -s)-$(uname -m)"
  echo "fetched=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$MARKER"

log "OK $(du -sh "$DEST" | cut -f1) → $DEST"
