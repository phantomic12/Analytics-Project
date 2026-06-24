"""Dataset profiler (Build Queue v2.1 Task 96).

The profiler composes the lazy plan and the summary computer into a
single, backend-agnostic :class:`DatasetProfile` producer.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from analytics_platform.contracts.common import Issue, RunId, Severity, StageId
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.profiling import DatasetProfile, ProfilingSpec
from analytics_platform.core import AnalyticsPlatformError, get_logger
from analytics_platform.profiling.summaries import compute_summaries

__all__ = ["Profiler", "ProfilerError", "profile_dataset"]


_LOGGER = get_logger(__name__)


class ProfilerError(AnalyticsPlatformError):
    """A typed profiler failure."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class Profiler:
    """Canonical dataset profiler."""

    def __init__(
        self,
        *,
        execution_limits: ExecutionLimitPolicy | None = None,
        spec: ProfilingSpec | None = None,
    ) -> None:
        self._execution_limits = execution_limits
        self._spec = spec or ProfilingSpec()

    def profile(
        self,
        dataset: DatasetHandle,
        data: Mapping[str, Sequence[Any]],
        *,
        run_id: RunId | None = None,
        stage_id: StageId | None = None,
    ) -> DatasetProfile:
        if not data:
            raise ProfilerError(
                Issue(
                    code="PROFILER_EMPTY_DATA",
                    severity=Severity.ERROR,
                    message="Cannot profile empty data.",
                    run_id=run_id,
                    stage_id=stage_id,
                )
            )
        return compute_summaries(
            data,
            dataset=dataset,
            execution_limits=self._execution_limits,
            spec=self._spec,
            run_id=run_id,
            stage_id=stage_id,
        )


def profile_dataset(
    dataset: DatasetHandle,
    data: Mapping[str, Sequence[Any]],
    *,
    execution_limits: ExecutionLimitPolicy | None = None,
    spec: ProfilingSpec | None = None,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> DatasetProfile:
    return Profiler(execution_limits=execution_limits, spec=spec).profile(
        dataset,
        data,
        run_id=run_id,
        stage_id=stage_id,
    )
