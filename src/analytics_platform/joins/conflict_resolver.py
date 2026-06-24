"""Conflict resolver (Build Queue v2.1 Task 117)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.joins import JoinSpec


class ConflictResolver:
    def resolve(self, spec: JoinSpec, conflicts: Sequence[str]) -> object:
        _ = spec, conflicts
        return []
