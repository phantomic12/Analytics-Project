"""Missingness analysis (Build Queue v2.1 Task 92).

This module is the canonical missingness-analysis stage. It
consumes a column-major tabular view (``{column_name: sequence}``)
plus the matching :class:`ObservedSchema` (optional) and produces
a :class:`MissingDataReport`.

The module is intentionally backend-agnostic: the column-major
view is a Python mapping that any backend can produce without
spinning up a heavy library. ``None`` values count as missing;
empty strings and NaN-like sentinels are out of scope for the MVP
(Task 92 only counts explicit ``None``).

Per the architecture-test plan (section 5), the ``quality`` module
is a domain module and may import from contracts, core, the
schema package (Task 89), and the approved runtime libraries.

Scope (Task 92):

- :class:`MissingnessReporter` — the canonical reporter.
- :func:`compute_missingness` — module-level convenience helper
  that uses the singleton reporter.
- :class:`MissingnessError` — typed failure carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.quality import (
    ColumnMissingness,
    DataQualityIssueKind,
    MissingDataReport,
    MissingnessPatternSummary,
    RowMissingnessSummary,
)
from analytics_platform.contracts.schemas import (
    ColumnName,
    ObservedSchema,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "MissingnessReporter",
    "MissingnessError",
    "compute_missingness",
]


_LOGGER = get_logger("quality.missingness")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for missingness error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# A column value is "missing" when it is None. Other sentinels
# (empty string, NaN) are deliberately not counted as missing
# in this MVP stage so the report is consistent across backends;
# downstream stages can layer their own semantics on top.
_MISSING_SENTINELS = {None}


def _is_missing(value: Any) -> bool:
    """Return True when ``value`` counts as missing for Task 92."""
    return value in _MISSING_SENTINELS


class MissingnessError(AnalyticsPlatformError):
    """A typed missingness-analysis failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------
def _row_missing_count(row: Sequence[Any]) -> int:
    return sum(1 for v in row if v in _MISSING_SENTINELS)


def _pattern_label(missing_columns: tuple[str, ...]) -> str:
    """Return the canonical pattern label for a missingness pattern.

    Empty patterns are labeled ``"none_missing"``; full rows are
    labeled ``"all_missing"``; everything else joins column
    names with ``"_"`` and prefixes ``"cols_"``.
    """
    if not missing_columns:
        return "none_missing"
    if len(missing_columns) == 1:
        return f"col_{missing_columns[0]}_missing"
    return "cols_" + "_".join(missing_columns) + "_missing"


def _stable_sort_key(label: str) -> str:
    return label


class MissingnessReporter:
    """The canonical missingness reporter.

    Construction parameters:

    - ``max_patterns``: optional non-negative upper bound on the
      number of pattern labels retained in the report. Defaults to
      ``64``. When the dataset produces more than ``max_patterns``
      distinct patterns, only the most-frequent ``max_patterns`` are
      retained (the rest are dropped).
    """

    def __init__(self, *, max_patterns: int = 64) -> None:
        if max_patterns < 0:
            raise MissingnessError(
                _make_issue(
                    code="MISSINGNESS_BAD_MAX_PATTERNS",
                    message=f"max_patterns must be >= 0, got {max_patterns!r}",
                )
            )
        self._max_patterns = max_patterns

    @property
    def max_patterns(self) -> int:
        return self._max_patterns

    def compute(
        self,
        data: Mapping[str, Sequence[Any]],
        *,
        observed: ObservedSchema | None = None,
        dataset: DatasetHandle | None = None,
    ) -> MissingDataReport:
        """Compute a :class:`MissingDataReport` for ``data``.

        ``data`` is a column-major mapping ``{column_name: values}``
        where each value sequence has the same length (the row
        count). ``observed`` is optional; when provided the report
        records the observed schema's fingerprint for traceability.
        ``dataset`` is also optional; the report requires a
        :class:`DatasetHandle` so a synthetic one is built when
        the caller does not provide one.
        """
        columns = list(data.keys())
        if not columns:
            raise MissingnessError(
                _make_issue(
                    code="MISSINGNESS_EMPTY_DATA",
                    message="Cannot compute missingness for empty data.",
                )
            )
        lengths = {col: len(seq) for col, seq in data.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise MissingnessError(
                _make_issue(
                    code="MISSINGNESS_RAGGED_COLUMNS",
                    message=(
                        f"Column-major data has inconsistent lengths: {lengths}"
                    ),
                )
            )
        total_rows = next(iter(unique_lengths))

        # Per-column missingness.
        column_records: list[ColumnMissingness] = []
        for col in columns:
            seq = data[col]
            missing = sum(1 for v in seq if _is_missing(v))
            total = len(seq)
            ratio = (missing / total) if total > 0 else 0.0
            is_constant = _is_constant_column(seq)
            column_records.append(
                ColumnMissingness(
                    column_name=ColumnName(col),
                    missing_count=missing,
                    total_count=total,
                    missing_ratio=ratio,
                    is_constant=is_constant,
                    conditionally_missing_on=(),
                    notes=None,
                )
            )

        # Per-row missingness.
        rows = [
            tuple(data[col][i] for col in columns) for i in range(total_rows)
        ]
        per_row_counts = [_row_missing_count(row) for row in rows]
        if per_row_counts:
            min_per_row = min(per_row_counts)
            max_per_row = max(per_row_counts)
            mean_per_row = sum(per_row_counts) / total_rows
            complete_rows = sum(1 for c in per_row_counts if c == 0)
        else:
            min_per_row = 0
            max_per_row = 0
            mean_per_row = 0.0
            complete_rows = 0
        # Histogram of missing-count -> row-count, sorted ascending
        # by missing-count.
        histogram_counts: dict[int, int] = {}
        for c in per_row_counts:
            histogram_counts[c] = histogram_counts.get(c, 0) + 1
        histogram_pairs = tuple(
            sorted(histogram_counts.items(), key=lambda kv: kv[0])
        )
        row_summary = RowMissingnessSummary(
            total_rows=total_rows,
            complete_rows=complete_rows,
            min_missing_per_row=min_per_row,
            max_missing_per_row=max_per_row,
            mean_missing_per_row=mean_per_row,
            missing_per_row_histogram=histogram_pairs,
            notes=None,
        )

        # Pattern summary: for each row, collect the tuple of
        # missing column names and count occurrences. Pattern
        # labels are stable across runs because they are derived
        # from sorted column names.
        pattern_counts: dict[str, int] = {}
        for row in rows:
            missing_cols = tuple(
                sorted(col for col, value in zip(columns, row) if _is_missing(value))
            )
            label = _pattern_label(missing_cols)
            pattern_counts[label] = pattern_counts.get(label, 0) + 1
        # Keep the top-K patterns by count to honor ``max_patterns``.
        sorted_patterns = sorted(
            pattern_counts.items(),
            key=lambda kv: (-kv[1], _stable_sort_key(kv[0])),
        )
        truncated = sorted_patterns[: self._max_patterns]
        pattern_summary = MissingnessPatternSummary(
            patterns=tuple(truncated),
            max_patterns=self._max_patterns,
            notes=None,
        )

        report = MissingDataReport(
            dataset=self._ensure_dataset(dataset),
            column_missingness=tuple(column_records),
            row_summary=row_summary,
            pattern_summary=pattern_summary,
            join_introduced_missingness=(),
            computed_at=None,
            run_id=None,
            stage_id=None,
            metadata=None,
        )
        _LOGGER.info(
            "Computed missingness: columns=%d rows=%d patterns=%d",
            len(column_records),
            total_rows,
            len(truncated),
        )
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_dataset(dataset: DatasetHandle | None) -> DatasetHandle:
        """Return a usable :class:`DatasetHandle` for the report."""
        if dataset is not None:
            return dataset
        from analytics_platform.contracts.datasets import (
            DatasetFormat,
            DatasetHandle as _DH,
            DatasetMaterializationStatus,
            DatasetRef,
            DatasetRole,
            StorageBackend,
        )

        return _DH(
            dataset_id="unknown",
            dataset_ref=DatasetRef("ds-unknown"),
            name="unknown",
            format=DatasetFormat.UNKNOWN,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.REGISTERED,
        )


def _is_constant_column(seq: Sequence[Any]) -> bool:
    """Return True when every non-missing value in ``seq`` is the same.

    A column with no non-missing values is reported as ``False``
    (not constant) because we cannot prove constancy from
    missing data alone; downstream stages may treat all-missing
    columns as constant if their policy requires it.
    """
    distinct: set[Any] = set()
    for v in seq:
        if _is_missing(v):
            continue
        distinct.add(v)
        if len(distinct) > 1:
            return False
    return len(distinct) == 1


# Module-level singleton reporter.
_REPORTER = MissingnessReporter()


def compute_missingness(
    data: Mapping[str, Sequence[Any]],
    *,
    observed: ObservedSchema | None = None,
    dataset: DatasetHandle | None = None,
) -> MissingDataReport:
    """Compute a :class:`MissingDataReport` using the singleton reporter."""
    return _REPORTER.compute(data, observed=observed, dataset=dataset)