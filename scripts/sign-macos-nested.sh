#!/usr/bin/env bash
# Signe les binaires imbriqués (Chromium helpers + sidecar) pour la notarization
# Apple. Sans identité : no-op (builds unsigned actuels).
#
# Usage:
#   CODESIGN_IDENTITY="Developer ID Application: Improba (TEAMID)" \
#     bash scripts/sign-macos-nested.sh path/to/Workproba.app
#
# Identité lue dans CODESIGN_IDENTITY ou CSC_IDENTITY.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER_ENTITLEMENTS="$ROOT_DIR/desktop/src-tauri/entitlements.chromium-helper.plist"
APP_ENTITLEMENTS="$ROOT_DIR/desktop/src-tauri/entitlements.plist"

IDENTITY="${CODESIGN_IDENTITY:-${CSC_IDENTITY:-}}"
TARGET="${1:-}"

log() { printf 'sign-macos-nested: %s\n' "$*"; }

if [[ "$(uname -s)" != "Darwin" ]]; then
  log "hors macOS, skip"
  exit 0
fi

if [[ -z "$IDENTITY" ]]; then
  log "pas d'identité (CODESIGN_IDENTITY), skip (build non signé)"
  exit 0
fi

if [[ -z "$TARGET" || ! -e "$TARGET" ]]; then
  log "usage: $0 path/to/Workproba.app" >&2
  exit 1
fi

if [[ ! -f "$HELPER_ENTITLEMENTS" || ! -f "$APP_ENTITLEMENTS" ]]; then
  log "entitlements manquants sous desktop/src-tauri/" >&2
  exit 1
fi

sign_one() {
  local path="$1"
  local entitlements="$2"
  codesign --force --options runtime --timestamp \
    --entitlements "$entitlements" \
    --sign "$IDENTITY" \
    "$path"
}

is_nested_sign_target() {
  local path="$1"
  local base
  base="$(basename "$path")"
  [[ "$path" == "$TARGET" ]] && return 1
  case "$base" in
    *.app|*.dylib|*.so|*.framework) return 0 ;;
    *Helper*|Chromium|chrome|chrome.exe|headless_shell|headless_shell.exe|chrome-headless-shell|chrome-headless-shell.exe|chrome_crashpad_handler)
      return 0
      ;;
    "Google Chrome for Testing") return 0 ;;
  esac
  [[ "$path" == *Frameworks* ]] && return 0
  return 1
}

# Du plus profond au plus superficiel (helpers Chromium avant le .app).
# awk+cut conserve les espaces dans les chemins (Chrome for Testing).
while IFS= read -r item; do
  [[ -n "$item" && -e "$item" ]] || continue
  is_nested_sign_target "$item" || continue
  log "helper $item"
  sign_one "$item" "$HELPER_ENTITLEMENTS"
done < <(
  find "$TARGET" \( \
    -name '*.app' -o -name '*.dylib' -o -name '*.so' -o -name '*.framework' \
    -o -name 'Google Chrome for Testing' -o -name 'Chromium' -o -name 'chrome' \
    -o -name '*Helper*' -o -name 'chrome_crashpad_handler' \
    -o -name 'chrome-headless-shell' -o -name 'headless_shell' \
  \) 2>/dev/null | awk '{ print length, $0 }' | sort -nr | cut -d' ' -f2-
)

sidecar="$(find "$TARGET" -name 'workproba-ai*' -type f 2>/dev/null | head -n 1 || true)"
if [[ -n "$sidecar" ]]; then
  log "sidecar $sidecar"
  sign_one "$sidecar" "$APP_ENTITLEMENTS"
fi

if [[ "$TARGET" == *.app ]]; then
  log "app $TARGET"
  sign_one "$TARGET" "$APP_ENTITLEMENTS"
  codesign --verify --deep --strict "$TARGET"
fi
log "OK"
