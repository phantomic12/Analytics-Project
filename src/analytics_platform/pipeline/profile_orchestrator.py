"""Profile-only orchestrator (Build Queue v2.1 Task 105)."""

from __future__ import annotations

from analytics_platform.contracts.common import RunId
from analytics_platform.contracts.pipeline import AnalysisPlan, AnalysisRunResult
from analytics_platform.contracts.registry import RunStatus
from analytics_platform.pipeline.profile_flow_executor import ProfileFlowExecutor


class ProfileOrchestrator:
    def __init__(self, executor: ProfileFlowExecutor | None = None) -> None:
        self._executor = executor or ProfileFlowExecutor()

    def run(self, plan: AnalysisPlan, run_id: str | None = None) -> AnalysisRunResult:
        stage_results = self._executor.execute(plan)
        succeeded = all(r.status == "succeeded" for r in stage_results)
        issues = tuple(issue for r in stage_results for issue in r.issues)
        warnings = tuple(w for r in stage_results for w in r.warnings)
        return AnalysisRunResult(
            run_id=RunId(run_id or "run-unknown"),
            status=RunStatus.SUCCEEDED if succeeded else RunStatus.FAILED,
            plan=plan,
            issues=issues,
            warnings=warnings,
        )

