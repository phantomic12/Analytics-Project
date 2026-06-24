"""Tests for the missing value handler (Build Queue v2.1 Task 121)."""

from __future__ import annotations

from analytics_platform.contracts.features import MissingValueStrategy
from analytics_platform.features.missing_value_handler import MissingValueHandler


class TestMissingValueHandler:
    def test_drop_row(self) -> None:
        handler = MissingValueHandler(strategy=MissingValueStrategy.DROP_ROW)
        result = handler.handle([1, None, 2, None, 3])
        assert result == [1, 2, 3]

    def test_impute_mean(self) -> None:
        handler = MissingValueHandler(strategy=MissingValueStrategy.IMPUTE_MEAN)
        result = handler.handle([2, None, 4])
        assert result == [2, 3, 4]
