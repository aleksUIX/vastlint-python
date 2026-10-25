#!/usr/bin/env bash

set -euo pipefail

REPO="aleksUIX/vastlint"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RELEASE_TAG="${1:-v$(cat "$REPO_ROOT/core-version.txt")}"

if [[ -z "$RELEASE_TAG" ]]; then
  echo "Usage: $0 <release-tag>  (e.g. v0.4.14)" >&2
  exit 1
fi

if [[ ! "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  echo "Expected a versioned engine release tag" >&2
  exit 1
fi

BASE_URL="https://github.com/${REPO}/releases/download/${RELEASE_TAG}"

VASTLINT_DOWNLOAD_DIR="$(mktemp -d)"
trap 'rm -rf "$VASTLINT_DOWNLOAD_DIR"' EXIT

while IFS='|' read -r TARBALL PLATFORM_DIR LIB_NAME; do
  [[ -n "$TARBALL" ]] || continue

  URL="${BASE_URL}/${TARBALL}"
  DEST_DIR="${REPO_ROOT}/src/vastlint/native/${PLATFORM_DIR}"
  UNPACK_DIR="${VASTLINT_DOWNLOAD_DIR}/${PLATFORM_DIR}"

  echo "→ Downloading ${TARBALL}"
  mkdir -p "$UNPACK_DIR" "$DEST_DIR"
  curl -fsSL "$URL" -o "${VASTLINT_DOWNLOAD_DIR}/${TARBALL}"
  tar xzf "${VASTLINT_DOWNLOAD_DIR}/${TARBALL}" -C "$UNPACK_DIR"

  cp "${UNPACK_DIR}/${LIB_NAME}" "${DEST_DIR}/${LIB_NAME}"
  chmod 755 "${DEST_DIR}/${LIB_NAME}"
  echo "  ✓ ${DEST_DIR}/${LIB_NAME}"
done <<'PLATFORMS'
vastlint-ffi-macos-aarch64.tar.gz|darwin_arm64|libvastlint.dylib
vastlint-ffi-macos-x86_64.tar.gz|darwin_amd64|libvastlint.dylib
vastlint-ffi-linux-aarch64.tar.gz|linux_arm64|libvastlint.so
vastlint-ffi-linux-x86_64.tar.gz|linux_amd64|libvastlint.so
PLATFORMS

python3 - "$REPO_ROOT" "$RELEASE_TAG" "$VASTLINT_DOWNLOAD_DIR" <<'PYMETA'
import hashlib,json,sys
from pathlib import Path
root,tag,downloads=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
subdir="src/vastlint/native"
platforms=[("macos-aarch64","darwin_arm64","dylib"),("macos-x86_64","darwin_amd64","dylib"),("linux-aarch64","linux_arm64","so"),("linux-x86_64","linux_amd64","so")]
files=[]
for platform,directory,extension in platforms:
    archive=f"vastlint-ffi-{platform}.tar.gz"
    library=Path(directory)/f"libvastlint.{extension}"
    files.append({"path":str(library),"sha256":hashlib.sha256((root/subdir/library).read_bytes()).hexdigest(),"source_url":f"https://github.com/aleksUIX/vastlint/releases/download/{tag}/{archive}","archive_sha256":hashlib.sha256((downloads/archive).read_bytes()).hexdigest()})
(root/subdir/"manifest.json").write_text(json.dumps({"engine_repository":"https://github.com/aleksUIX/vastlint","engine_version":tag.removeprefix("v"),"files":files},indent=2)+"\n")
(root/"core-version.txt").write_text(tag.removeprefix("v")+"\n")
PYMETA

echo
echo "Done. Vendored shared libraries updated to ${RELEASE_TAG}."
