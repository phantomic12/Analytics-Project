"""Association diagnostics (Build Queue v2.1 Task 97).

Diagnostic-only association checks. The MVP iterates over column
profiles produced by the profiling stage and emits a placeholder
:class:`PairwiseAssociationSummary` per numeric pair. Non-numeric
pairs are skipped with a :class:`AssociationWarning` so the stage
remains safe without a heavy statistical library.

The numerical computation is a real Pearson correlation on the
column-major values produced by the summary computer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from analytics_platform.contracts.associations import (
    AssociationCheckReport,
    AssociationCheckSpec,
    AssociationWarning,
    CorrelationMethod,
    PairwiseAssociationSummary,
)
from analytics_platform.contracts.common import Issue, RunId, Severity, StageId
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.profiling import DatasetProfile
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "AssociationDiagnostics",
    "AssociationDiagnosticsError",
    "run_association_checks",
]


_LOGGER = get_logger(__name__)


class AssociationDiagnosticsError(AnalyticsPlatformError):
    """A typed association-diagnostics failure."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    mean_x = sum(x[:n]) / n
    mean_y = sum(y[:n]) / n
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = sum((x[i] - mean_x) ** 2 for i in range(n)) ** 0.5
    den_y = sum((y[i] - mean_y) ** 2 for i in range(n)) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return abs(num / (den_x * den_y))


class AssociationDiagnostics:
    """Canonical diagnostic association checker."""

    def __init__(
        self,
        *,
        execution_limits: ExecutionLimitPolicy | None = None,
    ) -> None:
        self._execution_limits = execution_limits

    def run(
        self,
        dataset: DatasetHandle,
        profile: DatasetProfile,
        *,
        spec: AssociationCheckSpec | None = None,
        values: Mapping[str, Sequence[float]] | None = None,
        run_id: RunId | None = None,
        stage_id: StageId | None = None,
    ) -> AssociationCheckReport:
        spec = spec or AssociationCheckSpec()
        columns = sorted(cp.column_name for cp in profile.column_profiles)
        numeric_columns = {
            cp.column_name
            for cp in profile.column_profiles
            if cp.numeric is not None
        }
        summaries: list[PairwiseAssociationSummary] = []
        warnings: list[AssociationWarning] = []
        perfect_count = 0
        for i, a in enumerate(columns):
            for b in columns[i + 1:]:
                if a in numeric_columns and b in numeric_columns:
                    pair_values_x = (values or {}).get(a, [])
                    pair_values_y = (values or {}).get(b, [])
                    if len(pair_values_x) < 2 or len(pair_values_y) < 2:
                        warnings.append(
                            AssociationWarning(
                                code="ASSOCIATION_INSUFFICIENT_DATA",
                                severity=Severity.WARNING,
                                message=(
                                    f"Skipping association for {a!r}, {b!r}: not enough rows."
                                ),
                                column_a=a,
                                column_b=b,
                                run_id=run_id,
                                stage_id=stage_id,
                            )
                        )
                        continue
                    score = _pearson(pair_values_x, pair_values_y)
                    score = min(1.0, max(0.0, score))
                    is_perfect = score >= 1.0 - 1e-9
                    if is_perfect:
                        perfect_count += 1
                        score = 1.0
                    summary_kwargs = {
                        "column_a": a,
                        "column_b": b,
                        "method": CorrelationMethod.PEARSON,
                        "score": score,
                        "sample_size": min(len(pair_values_x), len(pair_values_y)),
                    }
                    if is_perfect:
                        summary_kwargs["is_perfect"] = True
                    summaries.append(PairwiseAssociationSummary(**summary_kwargs))
                else:
                    warnings.append(
                        AssociationWarning(
                            code="ASSOCIATION_SKIP_NON_NUMERIC",
                            severity=Severity.WARNING,
                            message=(
                                f"Skipping association for non-numeric pair {a!r}, {b!r}."
                            ),
                            column_a=a,
                            column_b=b,
                            run_id=run_id,
                            stage_id=stage_id,
                        )
                    )
        return AssociationCheckReport(
            dataset=dataset,
            spec=spec,
            pairwise_summaries=tuple(summaries),
            warnings=tuple(warnings),
            perfect_association_count=perfect_count,
            computed_at=datetime.now(),
            run_id=run_id,
            stage_id=stage_id,
        )


def run_association_checks(
    dataset: DatasetHandle,
    profile: DatasetProfile,
    *,
    spec: AssociationCheckSpec | None = None,
    values: Mapping[str, Sequence[float]] | None = None,
    execution_limits: ExecutionLimitPolicy | None = None,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> AssociationCheckReport:
    return AssociationDiagnostics(execution_limits=execution_limits).run(
        dataset,
        profile,
        spec=spec,
        values=values,
        run_id=run_id,
        stage_id=stage_id,
    )
