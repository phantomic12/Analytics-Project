"""Safe join executor (Build Queue v2.1 Task 118)."""

from __future__ import annotations

from array import array
from typing import Any

from analytics_platform.contracts.joins import JoinExecutionRequest, JoinValidationRequest
from analytics_platform.joins.conflict_resolver import ConflictResolver
from analytics_platform.joins.validator import JoinValidator


class RowBuffer:
    def __init__(self) -> None:
        self._rows: dict[str, list[Any]] = {}

    def append(self, row: dict[str, Any]) -> None:
        for key, value in row.items():
            self._rows.setdefault(key, []).append(value)

    def columns(self) -> tuple[str, ...]:
        return tuple(self._rows.keys())

    def take_rows(self, n: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        keys = self.columns()
        for idx in range(n):
            out.append({key: self._rows[key][idx] for key in keys})
        return out


class SafeJoinExecutor:
    def __init__(self) -> None:
        self._validator = JoinValidator()
        self._resolver = ConflictResolver()

    def execute(self, request: JoinExecutionRequest) -> RowBuffer:
        validation = JoinValidationRequest(spec=request.validation_report.spec)
        self._validator.validate(validation)
        return RowBuffer()
