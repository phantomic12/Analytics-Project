"""Tests for the lazy profiling plan (Build Queue v2.1 Task 95)."""

from __future__ import annotations

from analytics_platform.contracts.profiling import (
    ProfileApproximationMethod,
    ProfileComputationMode,
    ProfilingSpec,
)
from analytics_platform.profiling.lazy_profile_plan import (
    LazyProfilePlan,
    PlanDecision,
    build_lazy_profile_plan,
)


class TestBuildLazyProfilePlan:
    def test_safe_below_threshold(self) -> None:
        plan = build_lazy_profile_plan(dataset_rows=10)
        assert plan.decision is PlanDecision.SAFE
        assert plan.computation_mode is ProfileComputationMode.EXACT

    def test_approximate_above_threshold(self) -> None:
        spec = ProfilingSpec(approximate_above_row_count=100)
        plan = build_lazy_profile_plan(dataset_rows=200, spec=spec)
        assert plan.decision is PlanDecision.APPROXIMATE
        assert plan.computation_mode is ProfileComputationMode.APPROXIMATE
        assert plan.approximation_method is ProfileApproximationMethod.RESERVOIR_SAMPLING

    def test_default_spec_threshold_is_none(self) -> None:
        plan = build_lazy_profile_plan(dataset_rows=10_000_000)
        assert plan.decision is PlanDecision.SAFE
