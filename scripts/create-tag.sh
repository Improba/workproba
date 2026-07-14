#!/usr/bin/env bash
# Bump version across desktop artifacts and push tag vX.Y.Z to trigger desktop-release.yml.
#
# Usage:
#   ./scripts/create-tag.sh           # patch bump (default)
#   ./scripts/create-tag.sh minor
#   ./scripts/create-tag.sh major

set -euo pipefail

if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "This script must be run with bash" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required (apt install jq / brew install jq)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $ROOT" >&2
  exit 1
fi

if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
  echo "Working tree is not clean. Commit or stash changes before creating a release tag." >&2
  exit 1
fi

BRANCH="$(git -C "$ROOT" branch --show-current)"
if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
  echo "Warning: you are on branch '$BRANCH', not main/master." >&2
  if [[ -z "${CI:-}" && -t 0 ]]; then
    read -r -p "Continue? (y/N) " reply
    [[ "$reply" =~ ^[Yy]$ ]] || exit 1
  fi
fi

VERSION_TYPE="${1:-patch}"
if [[ "$VERSION_TYPE" != "major" && "$VERSION_TYPE" != "minor" && "$VERSION_TYPE" != "patch" ]]; then
  echo "Usage: $0 [patch|minor|major]" >&2
  exit 1
fi

read_version() {
  local file="$1"
  local mode="$2"
  case "$mode" in
    json) jq -r '.version' "$file" ;;
    toml) awk -F'"' '/^version = / { print $2; exit }' "$file" ;;
    *) echo "unknown mode: $mode" >&2; exit 1 ;;
  esac
}

VERSION_FILES=(
  "json:$ROOT/package.json"
  "json:$ROOT/front/package.json"
  "json:$ROOT/desktop/package.json"
  "json:$ROOT/desktop/src-tauri/tauri.conf.json"
  "toml:$ROOT/desktop/src-tauri/Cargo.toml"
  "toml:$ROOT/services/ai/pyproject.toml"
)

CURRENT=""
for entry in "${VERSION_FILES[@]}"; do
  mode="${entry%%:*}"
  file="${entry#*:}"
  version="$(read_version "$file" "$mode")"
  if [[ -z "$CURRENT" ]]; then
    CURRENT="$version"
  elif [[ "$version" != "$CURRENT" ]]; then
    echo "Version mismatch: $file has $version, expected $CURRENT" >&2
    echo "Align all version fields before running create-tag.sh." >&2
    exit 1
  fi
done

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"
case "$VERSION_TYPE" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac
NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
TAG="v${NEW_VERSION}"

if git -C "$ROOT" rev-parse --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
  echo "Tag ${TAG} already exists." >&2
  exit 1
fi

LATEST_TAG="$(git -C "$ROOT" tag -l 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1 || true)"
if [[ -n "$LATEST_TAG" ]]; then
  LATEST_VERSION="${LATEST_TAG#v}"
  if [[ "$(printf '%s\n' "$LATEST_VERSION" "$NEW_VERSION" | sort -V | tail -n1)" == "$LATEST_VERSION" && "$LATEST_VERSION" != "$NEW_VERSION" ]]; then
    echo "Warning: latest tag ($LATEST_TAG) is newer than planned release ($TAG)" >&2
    if [[ -z "${CI:-}" && -t 0 ]]; then
      read -r -p "Continue? (y/N) " reply
      [[ "$reply" =~ ^[Yy]$ ]] || exit 1
    fi
  fi
fi

echo "Bumping $CURRENT → $NEW_VERSION (tag $TAG)"

replace_json_version() {
  local file="$1"
  if [[ "$OSTYPE" == darwin* ]]; then
    sed -i '' "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/g" "$file"
  else
    sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/g" "$file"
  fi
}

replace_toml_version() {
  local file="$1"
  if [[ "$OSTYPE" == darwin* ]]; then
    sed -i '' "s/^version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" "$file"
  else
    sed -i "s/^version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" "$file"
  fi
}

replace_json_version "$ROOT/package.json"
replace_json_version "$ROOT/front/package.json"
replace_json_version "$ROOT/desktop/package.json"
replace_json_version "$ROOT/desktop/src-tauri/tauri.conf.json"
replace_toml_version "$ROOT/desktop/src-tauri/Cargo.toml"
replace_toml_version "$ROOT/services/ai/pyproject.toml"

git -C "$ROOT" add \
  package.json \
  front/package.json \
  desktop/package.json \
  desktop/src-tauri/tauri.conf.json \
  desktop/src-tauri/Cargo.toml \
  services/ai/pyproject.toml

git -C "$ROOT" commit -m "chore: bump version to $NEW_VERSION"
git -C "$ROOT" push
git -C "$ROOT" tag "$TAG"
git -C "$ROOT" push origin "$TAG"

echo "Done. GitHub Actions desktop-release will build $TAG."
