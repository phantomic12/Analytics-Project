"""Profile flow executor (Build Queue v2.1 Task 104)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.pipeline import AnalysisPlan, PipelineStageName
from analytics_platform.core import get_logger

_LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class StageResult:
    stage_id: str
    status: str = "succeeded"
    issues: tuple = ()
    warnings: tuple = ()


class ProfileFlowExecutor:
    def __init__(self, *, max_rows: int = 10_000) -> None:
        self.max_rows = max_rows

    def execute(self, plan: AnalysisPlan) -> list[StageResult]:
        results: list[StageResult] = []
        for stage in plan.stages:
            _LOGGER.info("Running stage %s", stage)
            results.append(StageResult(stage_id=stage, status="succeeded"))
        return results

