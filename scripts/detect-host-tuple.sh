#!/usr/bin/env bash
# Print the Rust target triple for the current host (used to name sidecar binaries).
set -euo pipefail

if command -v rustc >/dev/null 2>&1; then
  rustc --print host-tuple
  exit 0
fi

kernel="$(uname -s)"
arch="$(uname -m)"

case "$kernel" in
  Linux)
    case "$arch" in
      x86_64) echo "x86_64-unknown-linux-gnu" ;;
      aarch64|arm64) echo "aarch64-unknown-linux-gnu" ;;
      *) echo "unsupported Linux arch: $arch" >&2; exit 1 ;;
    esac
    ;;
  Darwin)
    case "$arch" in
      x86_64) echo "x86_64-apple-darwin" ;;
      arm64) echo "aarch64-apple-darwin" ;;
      *) echo "unsupported macOS arch: $arch" >&2; exit 1 ;;
    esac
    ;;
  MINGW* | MSYS* | CYGWIN* | Windows_NT)
    echo "x86_64-pc-windows-msvc"
    ;;
  *)
    echo "unsupported platform: $kernel" >&2
    exit 1
    ;;
esac
