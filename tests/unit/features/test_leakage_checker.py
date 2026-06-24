"""Tests for the leakage checker (Build Queue v2.1 Task 122)."""

from __future__ import annotations

from analytics_platform.features.leakage_checker import LeakageChecker


class TestLeakageChecker:
    def test_no_leakage(self) -> None:
        checker = LeakageChecker()
        risks = checker.check(["age", "income", "height"], "default")
        assert risks == []

    def test_detects_target_leakage(self) -> None:
        checker = LeakageChecker()
        risks = checker.check(["age", "default_amount", "height"], "default")
        assert len(risks) == 1
        assert risks[0].column_name == "default_amount"
