"""Integration test for the leakage checker (Build Queue v2.1 Task 122)."""

from __future__ import annotations

from analytics_platform.features.leakage_checker import LeakageChecker


class TestLeakageIntegration:
    def test_leakage_pipeline(self) -> None:
        checker = LeakageChecker()
        risks = checker.check(
            feature_names=["age", "default", "loan_amount"],
            target_name="default",
        )
        assert len(risks) == 1
        assert risks[0].column_name == "default"
