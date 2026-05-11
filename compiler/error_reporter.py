from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from compiler.limits import MAX_ERRORS


@dataclass
class CompileError:
    code: str
    message: str
    line: int
    column: int
    length: int
    severity: Literal['error', 'warning', 'info']
    suggestion: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            'code': self.code,
            'message': self.message,
            'line': self.line,
            'column': self.column,
            'length': self.length,
            'severity': self.severity,
        }
        if self.suggestion is not None:
            d['suggestion'] = self.suggestion
        return d


class ErrorReporter:
    def __init__(self) -> None:
        self.errors: list[CompileError] = []
        self.warnings: list[CompileError] = []

    def add(
        self,
        code: str,
        message: str,
        line: int,
        col: int,
        length: int = 1,
        severity: Literal['error', 'warning', 'info'] = 'error',
        suggestion: Optional[str] = None,
    ) -> None:
        entry = CompileError(
            code=code,
            message=message,
            line=line,
            column=col,
            length=length,
            severity=severity,
            suggestion=suggestion,
        )
        if severity == 'error':
            if len(self.errors) < MAX_ERRORS:
                self.errors.append(entry)
        else:
            self.warnings.append(entry)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def error_limit_reached(self) -> bool:
        return len(self.errors) >= MAX_ERRORS

    @property
    def all_issues(self) -> list[CompileError]:
        combined = self.errors + self.warnings
        return sorted(combined, key=lambda e: (e.line, e.column))

    def to_response(self, ok: Optional[bool] = None) -> dict[str, object]:
        resolved_ok = ok if ok is not None else not self.has_errors
        return {
            'ok': resolved_ok,
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
        }
