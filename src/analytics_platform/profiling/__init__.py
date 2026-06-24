"""Profiling package (Build Queue v2.1 Tasks 94-96)."""

from analytics_platform.profiling.summaries import (
    ProfilingSummaryComputer,
    ProfilingSummaryError,
    compute_summaries,
)
from analytics_platform.profiling.lazy_profile_plan import (
    PlanDecision,
    LazyProfilePlan,
    build_lazy_profile_plan,
)
from analytics_platform.profiling.profiler import (
    Profiler,
    ProfilerError,
    profile_dataset,
)

__all__ = [
    "ProfilingSummaryComputer",
    "ProfilingSummaryError",
    "compute_summaries",
    "PlanDecision",
    "LazyProfilePlan",
    "build_lazy_profile_plan",
    "Profiler",
    "ProfilerError",
    "profile_dataset",
]
