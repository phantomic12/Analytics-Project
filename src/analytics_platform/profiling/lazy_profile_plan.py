"""Lazy profiling plan (Build Queue v2.1 Task 95).

The lazy plan records the bounded decisions a profiling stage makes
before computing any summaries. The plan is a contract-light pydantic
model so the profile-only pipeline can serialise it for the run
manifest.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.profiling import (
    ProfileApproximationMethod,
    ProfileComputationMode,
    ProfilingSpec,
)

__all__ = [
    "PlanDecision",
    "LazyProfilePlan",
    "build_lazy_profile_plan",
]


class PlanDecision(str, Enum):
    """Result of evaluating a lazy profiling plan."""

    SAFE = "safe"
    APPROXIMATE = "approximate"
    SKIPPED = "skipped"


class LazyProfilePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    stage_id: str | None = None
    decision: PlanDecision = PlanDecision.SAFE
    reason: str | None = None
    computation_mode: ProfileComputationMode = ProfileComputationMode.EXACT
    approximation_method: ProfileApproximationMethod | None = None
    execution_limits: ExecutionLimitPolicy | None = None
    spec: ProfilingSpec | None = None


def build_lazy_profile_plan(
    *,
    dataset_rows: int,
    spec: ProfilingSpec | None = None,
    execution_limits: ExecutionLimitPolicy | None = None,
    run_id: str | None = None,
    stage_id: str | None = None,
) -> LazyProfilePlan:
    """Build a :class:`LazyProfilePlan` for the given row count.

    The MVP uses :attr:`ProfilingSpec.approximate_above_row_count` as
    the only escalation rule: when ``dataset_rows`` exceeds the
    threshold the plan flips to :attr:`PlanDecision.APPROXIMATE`.
    """
    spec = spec or ProfilingSpec()
    threshold = spec.approximate_above_row_count
    if threshold is not None and dataset_rows > threshold:
        return LazyProfilePlan(
            run_id=run_id,
            stage_id=stage_id,
            decision=PlanDecision.APPROXIMATE,
            reason="row_count_above_approximate_threshold",
            computation_mode=ProfileComputationMode.APPROXIMATE,
            approximation_method=ProfileApproximationMethod.RESERVOIR_SAMPLING,
            execution_limits=execution_limits,
            spec=spec,
        )
    return LazyProfilePlan(
        run_id=run_id,
        stage_id=stage_id,
        decision=PlanDecision.SAFE,
        computation_mode=ProfileComputationMode.EXACT,
        execution_limits=execution_limits,
        spec=spec,
    )
