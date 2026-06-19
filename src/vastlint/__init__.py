"""In-process Python bindings for vastlint VAST XML validation.

Wraps the stable ``vastlint-ffi`` C API backed by the same Rust core used by
the CLI, Go binding, Ruby gem, Erlang NIF, MCP server, and web validator.

    import vastlint

    result = vastlint.validate(vast_xml)
    if result.valid:
        print("clean tag")
    else:
        print(result.summary.errors, result.issues[0].message)
"""

from __future__ import annotations

from typing import Optional, Union

from ._library import _Library
from ._version import __version__
from .errors import LibraryError, VastlintError
from .result import Issue, Result, Summary

__all__ = [
    "validate",
    "version",
    "Result",
    "Issue",
    "Summary",
    "VastlintError",
    "LibraryError",
    "__version__",
]


def validate(
    xml: Union[str, bytes],
    *,
    wrapper_depth: int = 0,
    max_wrapper_depth: int = 5,
    rule_overrides: Optional[dict[str, str]] = None,
) -> Result:
    """Validate a VAST XML tag and return a structured :class:`Result`.

    ``rule_overrides`` maps rule IDs to severity levels, e.g.
    ``{"VAST-2.0-mediafile-https": "error", "VAST-4.1-mezzanine-recommended": "off"}``.
    """
    payload = _normalize_xml(xml)
    _validate_options(wrapper_depth, max_wrapper_depth, rule_overrides)

    return Result.from_json(
        _Library.instance().validate(
            payload,
            wrapper_depth=wrapper_depth,
            max_wrapper_depth=max_wrapper_depth,
            rule_overrides=rule_overrides,
        )
    )


def version() -> str:
    """Return the underlying vastlint-core version string."""
    return _Library.instance().version()


def _normalize_xml(xml: Union[str, bytes]) -> bytes:
    if isinstance(xml, str):
        payload = xml.encode("utf-8")
    elif isinstance(xml, (bytes, bytearray)):
        payload = bytes(xml)
    else:
        raise TypeError("xml must be a str or bytes")

    if not payload:
        raise ValueError("xml must not be empty")

    return payload


def _validate_options(
    wrapper_depth: int,
    max_wrapper_depth: int,
    rule_overrides: Optional[dict[str, str]],
) -> None:
    if not isinstance(wrapper_depth, int) or wrapper_depth < 0:
        raise ValueError("wrapper_depth must be an int >= 0")
    if not isinstance(max_wrapper_depth, int) or max_wrapper_depth < 0:
        raise ValueError("max_wrapper_depth must be an int >= 0")
    if rule_overrides is not None and not isinstance(rule_overrides, dict):
        raise TypeError("rule_overrides must be a dict or None")
