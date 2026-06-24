"""Data quality reporting (Build Queue v2.1 Task 93).

This module is the canonical data-quality reporting stage. It
consumes a column-major tabular view (same shape as Task 92) plus
the matching :class:`MissingDataReport` (or computes one on
demand) and produces a :class:`DataQualityReport` that wraps the
missingness summary with the broader
:class:`DataQualityIssue` / :class:`ModelExclusionSummary`
advisories.

The module is intentionally backend-agnostic: it operates on the
column-major mapping produced by
:func:`analytics_platform.quality.compute_missingness` and emits
typed contracts only.

Per the architecture-test plan (section 5), the ``quality`` module
is a domain module and may import from contracts, core, the
schema and semantics packages, and the approved runtime libraries.

Scope (Task 93):

- :class:`DataQualityReporter` — the canonical reporter.
- :func:`compute_data_quality` — module-level convenience helper
  that uses the singleton reporter.
- :class:`DataQualityError` — typed failure carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from analytics_platform.contracts.common import Issue, RunId, Severity, StageId
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.quality import (
    DataQualityIssue,
    DataQualityIssueKind,
    DataQualityReport,
    ModelExclusionReason,
    ModelExclusionSummary,
)
from analytics_platform.contracts.schemas import ColumnName, ObservedSchema
from analytics_platform.core import AnalyticsPlatformError, get_logger
from analytics_platform.quality.missingness import (
    MissingDataReport,
    MissingnessReporter,
    compute_missingness,
)

__all__ = [
    "DataQualityReporter",
    "DataQualityError",
    "compute_data_quality",
]


_LOGGER = get_logger("quality.data_quality")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for quality-reporting error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# Stable thresholds for the quality rules. The MVP keeps these as
# module-level constants so operators can override them via the
# reporter constructor.
DEFAULT_HIGH_MISSINGNESS_RATIO: float = 0.5
DEFAULT_NEAR_CONSTANT_RATIO: float = 0.99


def _column_distinct_ratio(seq: Sequence[Any]) -> float:
    """Return ``distinct_non_missing / total_non_missing`` for ``seq``."""
    total = 0
    distinct: set[Any] = set()
    for v in seq:
        if v is None:
            continue
        total += 1
        distinct.add(v)
    if total == 0:
        return 0.0
    return len(distinct) / total


class DataQualityError(AnalyticsPlatformError):
    """A typed data-quality-reporting failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------
class DataQualityReporter:
    """The canonical data-quality reporter.

    Construction parameters:

    - ``high_missingness_ratio``: non-negative ratio threshold at
      or above which a column is flagged with
      :attr:`DataQualityIssueKind.HIGH_MISSINGNESS`. Defaults to
      :data:`DEFAULT_HIGH_MISSINGNESS_RATIO`.
    - ``near_constant_ratio``: ratio threshold at or above which a
      column with very few distinct values is flagged
      :attr:`DataQualityIssueKind.NEAR_CONSTANT_COLUMN`. Defaults to
      :data:`DEFAULT_NEAR_CONSTANT_RATIO`.
    - ``missingness_reporter``: optional :class:`MissingnessReporter`
      used when the caller asks for a fresh missingness report.
    """

    def __init__(
        self,
        *,
        high_missingness_ratio: float = DEFAULT_HIGH_MISSINGNESS_RATIO,
        near_constant_ratio: float = DEFAULT_NEAR_CONSTANT_RATIO,
        missingness_reporter: MissingnessReporter | None = None,
    ) -> None:
        if not 0.0 <= high_missingness_ratio <= 1.0:
            raise DataQualityError(
                _make_issue(
                    code="QUALITY_BAD_HIGH_MISSINGNESS_RATIO",
                    message=(
                        "high_missingness_ratio must be in [0.0, 1.0], "
                        f"got {high_missingness_ratio!r}"
                    ),
                )
            )
        if not 0.0 <= near_constant_ratio <= 1.0:
            raise DataQualityError(
                _make_issue(
                    code="QUALITY_BAD_NEAR_CONSTANT_RATIO",
                    message=(
                        "near_constant_ratio must be in [0.0, 1.0], "
                        f"got {near_constant_ratio!r}"
                    ),
                )
            )
        self._high_missingness_ratio = high_missingness_ratio
        self._near_constant_ratio = near_constant_ratio
        self._missingness_reporter = missingness_reporter or MissingnessReporter()

    @property
    def high_missingness_ratio(self) -> float:
        return self._high_missingness_ratio

    @property
    def near_constant_ratio(self) -> float:
        return self._near_constant_ratio

    def compute(
        self,
        data: Mapping[str, Sequence[Any]],
        *,
        observed: ObservedSchema | None = None,
        dataset: DatasetHandle | None = None,
        missingness_report: MissingDataReport | None = None,
        run_id: RunId | None = None,
        stage_id: StageId | None = None,
    ) -> DataQualityReport:
        """Compute a :class:`DataQualityReport` for ``data``.

        When ``missingness_report`` is omitted, the reporter
        computes one via :func:`compute_missingness`.
        ``observed`` is forwarded to the missingness computation
        when relevant.
        """
        if missingness_report is None:
            missingness_report = self._missingness_reporter.compute(
                data, observed=observed, dataset=dataset
            )

        quality_issues: list[DataQualityIssue] = []
        # Dedup model_exclusions by column name + reason: a column
        # may trigger multiple rules (e.g. both high-missingness
        # and constant-column) but the contract requires unique
        # column names. We keep the most-severe reason per column.
        exclusion_index: dict[ColumnName, ModelExclusionSummary] = {}
        for cm in missingness_report.column_missingness:
            col_name = ColumnName(cm.column_name)
            if (
                cm.missing_ratio is not None
                and cm.missing_ratio >= self._high_missingness_ratio
            ):
                quality_issues.append(
                    self._make_high_missingness_issue(
                        col_name, cm, run_id=run_id, stage_id=stage_id
                    )
                )
                exclusion_index[col_name] = ModelExclusionSummary(
                    column_name=col_name,
                    reason=ModelExclusionReason.HIGH_MISSINGNESS,
                    detail=(
                        f"Column has missingness ratio "
                        f"{cm.missing_ratio:.3f} (threshold "
                        f"{self._high_missingness_ratio:.3f})."
                    ),
                    missing_ratio=cm.missing_ratio,
                    run_id=run_id,
                    stage_id=stage_id,
                )
            if cm.is_constant is True:
                quality_issues.append(
                    self._make_constant_column_issue(
                        col_name,
                        run_id=run_id,
                        stage_id=stage_id,
                    )
                )
                # Constant_column is more severe than
                # high_missingness; overwrite only when the entry
                # is missing or has a less-severe reason.
                existing = exclusion_index.get(col_name)
                if existing is None or existing.reason is not ModelExclusionReason.CONSTANT_COLUMN:
                    exclusion_index[col_name] = ModelExclusionSummary(
                        column_name=col_name,
                        reason=ModelExclusionReason.CONSTANT_COLUMN,
                        detail="Column has only one distinct non-missing value.",
                        missing_ratio=cm.missing_ratio,
                        run_id=run_id,
                        stage_id=stage_id,
                    )
            elif cm.total_count is not None and cm.total_count > 0:
                seq = data.get(cm.column_name, ())
                ratio = _column_distinct_ratio(seq)
                if ratio > 0.0 and ratio <= (1.0 - self._near_constant_ratio):
                    quality_issues.append(
                        self._make_near_constant_issue(
                            col_name,
                            ratio,
                            run_id=run_id,
                            stage_id=stage_id,
                        )
                    )
                    # Only set the exclusion when no more-severe
                    # reason is already present.
                    existing = exclusion_index.get(col_name)
                    if existing is None:
                        exclusion_index[col_name] = ModelExclusionSummary(
                            column_name=col_name,
                            reason=ModelExclusionReason.NEAR_CONSTANT,
                            detail=(
                                f"Column has distinct ratio {ratio:.3f} "
                                f"(threshold {1.0 - self._near_constant_ratio:.3f})."
                            ),
                            missing_ratio=cm.missing_ratio,
                            run_id=run_id,
                            stage_id=stage_id,
                        )
        model_exclusions = list(exclusion_index.values())

        is_clean = not any(
            i.severity in (Severity.ERROR, Severity.CRITICAL) for i in quality_issues
        )
        report = DataQualityReport(
            dataset=missingness_report.dataset,
            missing_data=missingness_report,
            quality_issues=tuple(quality_issues),
            model_exclusions=tuple(model_exclusions),
            has_target_associated_missingness=None,
            is_passthrough_clean=is_clean if quality_issues else None,
            issues=(),
            warnings=(),
            computed_at=None,
            run_id=run_id,
            stage_id=stage_id,
            metadata=None,
        )
        _LOGGER.info(
            "Computed data quality: issues=%d exclusions=%d passthrough_clean=%s",
            len(quality_issues),
            len(model_exclusions),
            report.is_passthrough_clean,
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_high_missingness_issue(
        column_name: ColumnName,
        cm: Any,
        *,
        run_id: RunId | None,
        stage_id: StageId | None,
    ) -> DataQualityIssue:
        return DataQualityIssue(
            code="COL_HIGH_MISSINGNESS",
            kind=DataQualityIssueKind.HIGH_MISSINGNESS,
            severity=Severity.WARNING,
            message=(
                f"Column {column_name!r} has high missingness "
                f"(ratio={cm.missing_ratio:.3f})."
            ),
            column_name=column_name,
            observed_value=f"missing_ratio={cm.missing_ratio:.3f}",
            threshold=f"{cm.total_count}",
            row_count_affected=cm.missing_count,
            run_id=run_id,
            stage_id=stage_id,
            context=None,
        )

    @staticmethod
    def _make_constant_column_issue(
        column_name: ColumnName,
        *,
        run_id: RunId | None,
        stage_id: StageId | None,
    ) -> DataQualityIssue:
        return DataQualityIssue(
            code="COL_CONSTANT",
            kind=DataQualityIssueKind.CONSTANT_COLUMN,
            severity=Severity.WARNING,
            message=(
                f"Column {column_name!r} has only one distinct non-missing value."
            ),
            column_name=column_name,
            observed_value="distinct_count=1",
            threshold="distinct_count>1",
            row_count_affected=None,
            run_id=run_id,
            stage_id=stage_id,
            context=None,
        )

    @staticmethod
    def _make_near_constant_issue(
        column_name: ColumnName,
        ratio: float,
        *,
        run_id: RunId | None,
        stage_id: StageId | None,
    ) -> DataQualityIssue:
        return DataQualityIssue(
            code="COL_NEAR_CONSTANT",
            kind=DataQualityIssueKind.NEAR_CONSTANT_COLUMN,
            severity=Severity.WARNING,
            message=(
                f"Column {column_name!r} is near-constant "
                f"(distinct ratio={ratio:.3f})."
            ),
            column_name=column_name,
            observed_value=f"distinct_ratio={ratio:.3f}",
            threshold="distinct_ratio>0.01",
            row_count_affected=None,
            run_id=run_id,
            stage_id=stage_id,
            context=None,
        )


# Module-level singleton reporter.
_REPORTER = DataQualityReporter()


def compute_data_quality(
    data: Mapping[str, Sequence[Any]],
    *,
    observed: ObservedSchema | None = None,
    dataset: DatasetHandle | None = None,
    missingness_report: MissingDataReport | None = None,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> DataQualityReport:
    """Compute a :class:`DataQualityReport` using the singleton reporter."""
    return _REPORTER.compute(
        data,
        observed=observed,
        dataset=dataset,
        missingness_report=missingness_report,
        run_id=run_id,
        stage_id=stage_id,
    )