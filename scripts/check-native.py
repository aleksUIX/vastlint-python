#!/usr/bin/env python3
"""Check the bundled engine files independently of sibling source checkouts."""
import ctypes
import hashlib
import json
import platform
from pathlib import Path

root = Path(__file__).resolve().parent.parent
native = root / "src/vastlint/native"
manifest = json.loads((native / "manifest.json").read_text())
expected = (root / "core-version.txt").read_text().strip()
assert manifest["engine_version"] == expected, "engine pin and native manifest differ"
assert len(manifest["files"]) == 4, "all four supported platforms must be bundled"
for entry in manifest["files"]:
    path = native / entry["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], str(path)
for name in ["LICENSE", "NOTICE"]:
    assert (root / name).is_file(), f"missing {name}"
system = platform.system()
architecture = platform.machine().lower()
directory = {("Darwin", "arm64"): "darwin_arm64", ("Darwin", "x86_64"): "darwin_amd64", ("Linux", "aarch64"): "linux_arm64", ("Linux", "x86_64"): "linux_amd64"}.get((system, architecture))
if directory:
    extension = "dylib" if system == "Darwin" else "so"
    library = ctypes.CDLL(str(native / directory / f"libvastlint.{extension}"))
    library.vastlint_version.restype = ctypes.c_char_p
    actual = library.vastlint_version().decode()
    assert actual == expected, f"bundled engine reports {actual}, expected {expected}"
print(f"Bundled VASTlint {expected}: four hashes, runtime version and attribution verified.")
