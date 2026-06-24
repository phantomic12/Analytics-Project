"""Leakage checker (Build Queue v2.1 Task 122)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.common import Severity
from analytics_platform.contracts.features import (
    ColumnName,
    LeakageRisk,
    LeakageRiskType,
)


class LeakageChecker:
    def check(self, feature_names: Sequence[str], target_name: str) -> Sequence[LeakageRisk]:
        found: list[LeakageRisk] = []
        for feature in feature_names:
            if target_name.lower() in feature.lower():
                found.append(
                    LeakageRisk(
                        column_name=ColumnName(feature),
                        risk_type=LeakageRiskType.TARGET_AS_FEATURE,
                        severity=Severity.ERROR,
                        message=f"target {target_name!r} appears in feature {feature!r}",
                    )
                )
        return found
