from __future__ import annotations

import ctypes
import json
import os
import platform
import threading
from pathlib import Path
from typing import Optional

from .errors import LibraryError

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent  # .../vastlint-python


def _extension() -> str:
    return "dylib" if platform.system() == "Darwin" else "so"


def _platform_directory() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    intel = machine in ("x86_64", "amd64")

    if system == "Darwin":
        if arm:
            return "darwin_arm64"
        if intel:
            return "darwin_amd64"
    elif system == "Linux":
        if arm:
            return "linux_arm64"
        if intel:
            return "linux_amd64"

    raise LibraryError(f"unsupported platform {system}/{machine}")


def _candidate_paths() -> list[Path]:
    candidates: list[Optional[Path]] = []

    env_path = os.environ.get("VASTLINT_LIB_PATH")
    if env_path:
        candidates.append(Path(env_path))

    filename = f"libvastlint.{_extension()}"
    candidates.append(_HERE / "native" / _platform_directory() / filename)

    # development fallback: sibling vastlint Rust workspace
    sibling = _REPO_ROOT.parent / "vastlint"
    ext = _extension()
    candidates.append(sibling / "target" / "debug" / f"libvastlint_ffi.{ext}")
    candidates.append(sibling / "target" / "release" / f"libvastlint_ffi.{ext}")

    return [c for c in candidates if c is not None]


def _resolve_path() -> Path:
    candidates = _candidate_paths()
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    looked = "\n".join(f"  - {c}" for c in candidates)
    raise LibraryError(
        "unable to find libvastlint for "
        f"{platform.system()}/{platform.machine()}\nlooked in:\n{looked}\n"
        "set VASTLINT_LIB_PATH or vendor a release library under src/vastlint/native"
    )


class _Library:
    _instance: Optional["_Library"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        path = _resolve_path()
        try:
            lib = ctypes.CDLL(str(path))
        except OSError as error:
            raise LibraryError(f"failed to load {path}: {error}") from error

        lib.vastlint_validate.restype = ctypes.c_void_p
        lib.vastlint_validate.argtypes = [ctypes.c_char_p, ctypes.c_size_t]

        lib.vastlint_validate_with_options.restype = ctypes.c_void_p
        lib.vastlint_validate_with_options.argtypes = [
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_char_p,
        ]

        lib.vastlint_result_json.restype = ctypes.c_char_p
        lib.vastlint_result_json.argtypes = [ctypes.c_void_p]

        lib.vastlint_result_free.restype = None
        lib.vastlint_result_free.argtypes = [ctypes.c_void_p]

        lib.vastlint_version.restype = ctypes.c_char_p
        lib.vastlint_version.argtypes = []

        self._lib = lib
        self.path = path

    @classmethod
    def instance(cls) -> "_Library":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def validate(
        self,
        xml: bytes,
        wrapper_depth: int,
        max_wrapper_depth: int,
        rule_overrides: Optional[dict[str, str]],
    ) -> str:
        if self._is_default_call(wrapper_depth, max_wrapper_depth, rule_overrides):
            raw = self._lib.vastlint_validate(xml, len(xml))
        else:
            overrides = (
                json.dumps(rule_overrides).encode("utf-8") if rule_overrides else None
            )
            raw = self._lib.vastlint_validate_with_options(
                xml, len(xml), wrapper_depth, max_wrapper_depth, overrides
            )

        if not raw:
            raise LibraryError("vastlint returned NULL")

        try:
            payload = self._lib.vastlint_result_json(raw)
            if not payload:
                raise LibraryError("vastlint_result_json returned NULL")
            return payload.decode("utf-8")
        finally:
            self._lib.vastlint_result_free(raw)

    def version(self) -> str:
        payload = self._lib.vastlint_version()
        if not payload:
            raise LibraryError("vastlint_version returned NULL")
        return payload.decode("utf-8")

    @staticmethod
    def _is_default_call(
        wrapper_depth: int,
        max_wrapper_depth: int,
        rule_overrides: Optional[dict[str, str]],
    ) -> bool:
        return (
            wrapper_depth == 0
            and max_wrapper_depth == 5
            and not rule_overrides
        )
