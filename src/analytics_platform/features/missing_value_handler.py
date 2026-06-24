"""Missing value handler (Build Queue v2.1 Task 121)."""

from __future__ import annotations

from typing import Any, Sequence

from analytics_platform.contracts.features import MissingValueStrategy


class MissingValueHandler:
    def __init__(self, strategy: MissingValueStrategy = MissingValueStrategy.DROP_ROW) -> None:
        self._strategy = strategy

    def handle(self, values: Sequence[Any]) -> list[Any]:
        if self._strategy is MissingValueStrategy.DROP_ROW:
            return [value for value in values if value is not None]
        if self._strategy is MissingValueStrategy.IMPUTE_MEAN:
            clean = [value for value in values if value is not None]
            if not clean:
                return list(values)
            mean = sum(clean) / len(clean)
            return [value if value is not None else mean for value in values]
        return list(values)
