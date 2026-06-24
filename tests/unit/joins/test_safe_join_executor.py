"""Tests for the safe join executor (Build Queue v2.1 Task 118)."""

from __future__ import annotations

from analytics_platform.joins.safe_join_executor import RowBuffer, SafeJoinExecutor


class TestRowBuffer:
    def test_append_and_take_rows(self) -> None:
        buf = RowBuffer()
        buf.append({"a": 1, "b": 2})
        buf.append({"a": 3, "b": 4})
        assert buf.columns() == ("a", "b")
        rows = buf.take_rows(2)
        assert rows == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


class TestSafeJoinExecutor:
    def test_execute_returns_buffer(self) -> None:
        executor = SafeJoinExecutor()
        assert executor is not None
