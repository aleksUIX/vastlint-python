#!/usr/bin/env bash

set -euo pipefail

REPO="aleksUIX/vastlint"
RELEASE_TAG="${1:-}"

if [[ -z "$RELEASE_TAG" ]]; then
  echo "Usage: $0 <release-tag>  (e.g. v0.4.14)" >&2
  exit 1
fi

BASE_URL="https://github.com/${REPO}/releases/download/${RELEASE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

while IFS='|' read -r TARBALL PLATFORM_DIR LIB_NAME; do
  [[ -n "$TARBALL" ]] || continue

  URL="${BASE_URL}/${TARBALL}"
  DEST_DIR="${REPO_ROOT}/src/vastlint/native/${PLATFORM_DIR}"
  UNPACK_DIR="${TMPDIR}/${PLATFORM_DIR}"

  echo "→ Downloading ${TARBALL}"
  mkdir -p "$UNPACK_DIR" "$DEST_DIR"
  curl -fsSL "$URL" -o "${TMPDIR}/${TARBALL}"
  tar xzf "${TMPDIR}/${TARBALL}" -C "$UNPACK_DIR"

  cp "${UNPACK_DIR}/${LIB_NAME}" "${DEST_DIR}/${LIB_NAME}"
  chmod 755 "${DEST_DIR}/${LIB_NAME}"
  echo "  ✓ ${DEST_DIR}/${LIB_NAME}"
done <<'PLATFORMS'
vastlint-ffi-macos-aarch64.tar.gz|darwin_arm64|libvastlint.dylib
vastlint-ffi-macos-x86_64.tar.gz|darwin_amd64|libvastlint.dylib
vastlint-ffi-linux-aarch64.tar.gz|linux_arm64|libvastlint.so
vastlint-ffi-linux-x86_64.tar.gz|linux_amd64|libvastlint.so
PLATFORMS

echo
echo "Done. Vendored shared libraries updated to ${RELEASE_TAG}."
