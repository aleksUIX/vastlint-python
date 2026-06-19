from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .errors import LibraryError


@dataclass(frozen=True)
class Issue:
    id: str
    severity: str
    message: str
    path: Optional[str] = None
    spec_ref: Optional[str] = None
    line: Optional[int] = None
    col: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "spec_ref": self.spec_ref,
            "line": self.line,
            "col": self.col,
        }


@dataclass(frozen=True)
class Summary:
    errors: int
    warnings: int
    infos: int
    valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "valid": self.valid,
        }


@dataclass(frozen=True)
class Result:
    version: Optional[str]
    issues: list[Issue]
    summary: Summary

    @property
    def valid(self) -> bool:
        return self.summary.valid

    @classmethod
    def from_json(cls, payload: str) -> "Result":
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as error:
            raise LibraryError(f"failed to parse vastlint result JSON: {error}") from error

        try:
            summary = parsed["summary"]
            return cls(
                version=parsed.get("version"),
                issues=[
                    Issue(
                        id=issue["id"],
                        severity=issue["severity"],
                        message=issue["message"],
                        path=issue.get("path"),
                        spec_ref=issue.get("spec_ref"),
                        line=issue.get("line"),
                        col=issue.get("col"),
                    )
                    for issue in parsed.get("issues") or []
                ],
                summary=Summary(
                    errors=summary["errors"],
                    warnings=summary["warnings"],
                    infos=summary["infos"],
                    valid=summary["valid"],
                ),
            )
        except (KeyError, TypeError) as error:
            raise LibraryError(f"unexpected vastlint result shape: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": self.summary.to_dict(),
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)
