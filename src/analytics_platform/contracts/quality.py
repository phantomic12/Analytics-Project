"""Data quality and missingness contracts (Build Queue v2.1 Task 24).

Public contracts for the ``quality`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Quality contracts describe
the typed output of stage 4.7 (data quality and missingness report):
how many values are missing per column, how many rows are missing
values, what patterns of missingness the report detected, and what the
quality findings mean for downstream stages (joins, modeling,
validation, reporting). They are dependency-light and never embed raw
dataframes, file bytes, or backend objects.

Scope:

- ``DataQualityReport`` — overall quality summary for a dataset.
- ``MissingDataReport`` — per-column + per-row missingness detail.
- ``ColumnMissingness`` — per-column missingness statistics.
- ``RowMissingnessSummary`` — per-row missingness summary statistics.
- ``MissingnessPatternSummary`` — categorical pattern counts for
  missingness (e.g. ``"only_col_a_missing"``).
- ``JoinIntroducedMissingness`` — typed per-column missingness that
  appeared after a join.
- ``ModelExclusionSummary`` — typed per-column reason why a column was
  excluded from modeling.
- ``DataQualityIssue`` — typed per-column / per-row quality issue.

Not implemented here: actual missing-data / quality computation. The
quality stage is deferred to later implementation tasks and must
consume these contracts only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import ColumnName

__all__ = [
    "DataQualityReport",
    "MissingDataReport",
    "ColumnMissingness",
    "RowMissingnessSummary",
    "MissingnessPatternSummary",
    "JoinIntroducedMissingness",
    "ModelExclusionSummary",
    "DataQualityIssue",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _QualityContractModel(BaseModel):
    """Base configuration for quality contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, file bytes, or
    backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for missingness fractions. The bounds
# are enforced at the type-alias level so consumers can rely on the
# range.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Per-column / per-row summaries
# ===========================================================================
class ColumnMissingness(_QualityContractModel):
    """Per-column missingness statistics for a single column.

    A column-missingness record reports the count and bounded fraction
    of missing values in a single column, plus optional auxiliary
    statistics (e.g. "missing only when column X is missing"). It must
    not embed raw column data or sample values.

    Fields:

    - ``column_name``: :data:`ColumnName` of the column.
    - ``missing_count``: optional non-negative count of missing values.
    - ``total_count``: optional non-negative count of total values
      observed for the column.
    - ``missing_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``is_constant``: optional flag indicating the column has only one
      distinct non-null value.
    - ``conditionally_missing_on``: optional tuple of :data:`ColumnName`
      indicating that this column is missing whenever any of the named
      columns is also missing (a coarse "conditionally missing" hint).
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ..., description="ColumnName of the column."
    )
    missing_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of missing values.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed for the column.",
    )
    missing_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded missingness ratio in [0.0, 1.0].",
    )
    is_constant: bool | None = Field(
        default=None,
        description="Optional flag indicating the column has only one distinct non-null value.",
    )
    conditionally_missing_on: tuple[ColumnName, ...] = Field(
        default=(),
        description="Optional tuple of ColumnName the column is conditionally missing on.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _missing_count_does_not_exceed_total(self) -> "ColumnMissingness":
        if (
            self.missing_count is not None
            and self.total_count is not None
            and self.missing_count > self.total_count
        ):
            raise ValueError(
                "ColumnMissingness.missing_count must not exceed total_count."
            )
        return self


class RowMissingnessSummary(_QualityContractModel):
    """Per-row missingness summary statistics for a dataset.

    A row-missingness summary captures the distribution of "how many
    columns are missing per row" via a bounded histogram
    (``missing_count -> row_count``) plus the bounded minimum, maximum,
    mean, and total row count.

    Fields:

    - ``total_rows``: optional non-negative total row count.
    - ``complete_rows``: optional non-negative count of rows with no
      missing values.
    - ``min_missing_per_row``: optional non-negative minimum number of
      missing values observed in any single row.
    - ``max_missing_per_row``: optional non-negative maximum number of
      missing values observed in any single row.
    - ``mean_missing_per_row``: optional bounded mean number of
      missing values per row (in ``[0.0, +inf)``; the
      ``missing-per-row`` is bounded by the number of columns).
    - ``missing_per_row_histogram``: optional tuple of
      ``(missing_count, row_count)`` pairs in deterministic insertion
      order. ``missing_count`` values are non-negative and unique.
    - ``notes``: optional bounded human-readable note.
    """

    total_rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative total row count.",
    )
    complete_rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of rows with no missing values.",
    )
    min_missing_per_row: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative minimum number of missing values per row.",
    )
    max_missing_per_row: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative maximum number of missing values per row.",
    )
    mean_missing_per_row: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional bounded mean number of missing values per row.",
    )
    missing_per_row_histogram: tuple[tuple[int, int], ...] = Field(
        default=(),
        description="Optional tuple of (missing_count, row_count) histogram pairs.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _complete_rows_does_not_exceed_total(self) -> "RowMissingnessSummary":
        if (
            self.total_rows is not None
            and self.complete_rows is not None
            and self.complete_rows > self.total_rows
        ):
            raise ValueError(
                "RowMissingnessSummary.complete_rows must not exceed total_rows."
            )
        return self

    @model_validator(mode="after")
    def _min_max_consistent(self) -> "RowMissingnessSummary":
        if (
            self.min_missing_per_row is not None
            and self.max_missing_per_row is not None
            and self.max_missing_per_row < self.min_missing_per_row
        ):
            raise ValueError(
                "RowMissingnessSummary.max_missing_per_row must be >= min_missing_per_row."
            )
        return self

    @model_validator(mode="after")
    def _histogram_keys_unique_and_ordered(self) -> "RowMissingnessSummary":
        seen: set[int] = set()
        last: int | None = None
        for missing_count, row_count in self.missing_per_row_histogram:
            if missing_count < 0:
                raise ValueError(
                    "RowMissingnessSummary histogram missing_count must be non-negative."
                )
            if row_count < 0:
                raise ValueError(
                    "RowMissingnessSummary histogram row_count must be non-negative."
                )
            if missing_count in seen:
                raise ValueError(
                    "RowMissingnessSummary histogram must have unique missing_count keys."
                )
            if last is not None and missing_count <= last:
                raise ValueError(
                    "RowMissingnessSummary histogram missing_count keys must be strictly increasing."
                )
            seen.add(missing_count)
            last = missing_count
        return self


class MissingnessPatternSummary(_QualityContractModel):
    """A categorical pattern-count summary for missingness.

    A missingness-pattern summary is a small, bounded list of
    ``(pattern, count)`` pairs describing how often each missingness
    pattern was observed. The ``pattern`` is a free-form string label
    produced by the quality stage (e.g. ``"only_col_a_missing"`` or
    ``"a_and_b_missing"``). Patterns are not interpreted by the
    contract; they are a discovery aid for reporting.

    Fields:

    - ``patterns``: tuple of ``(pattern, count)`` pairs. ``pattern``
      labels are bounded strings; ``count`` values are non-negative
      integers. Pattern labels are unique.
    - ``max_patterns``: optional non-negative upper bound on the
      number of patterns considered (e.g. ``top_k``). When the
      contract holds ``k``+1 patterns the value lets consumers know
      that some patterns were truncated.
    - ``notes``: optional bounded human-readable note.
    """

    patterns: tuple[tuple[str, int], ...] = Field(
        default=(),
        description="Tuple of (pattern, count) pairs.",
    )
    max_patterns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of patterns considered.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _pattern_labels_unique_and_bounded(self) -> "MissingnessPatternSummary":
        seen_labels: set[str] = set()
        for pattern, count in self.patterns:
            if not pattern or len(pattern) > 256:
                raise ValueError(
                    "MissingnessPatternSummary pattern labels must be non-empty "
                    "and <= 256 characters."
                )
            if count < 0:
                raise ValueError(
                    "MissingnessPatternSummary counts must be non-negative."
                )
            if pattern in seen_labels:
                raise ValueError(
                    f"MissingnessPatternSummary has duplicate pattern label: {pattern!r}."
                )
            seen_labels.add(pattern)
        if self.max_patterns is not None and len(self.patterns) > self.max_patterns:
            raise ValueError(
                "MissingnessPatternSummary.patterns has more entries than max_patterns."
            )
        return self


# ===========================================================================
# JoinIntroducedMissingness
# ===========================================================================
class JoinIntroducedMissingness(_QualityContractModel):
    """Typed per-column missingness that appeared after a join.

    Join-introduced missingness captures the column-level missingness
    that a join operation *created* (i.e. was not present in the left
    input but appeared in the joined output). The contract is per-column
    and is consumed by joins, features, and reporting.

    Fields:

    - ``column_name``: :data:`ColumnName` of the column.
    - ``introduced_missing_count``: optional non-negative count of
      missing values introduced by the join.
    - ``total_count``: optional non-negative count of total values
      observed for the column after the join.
    - ``introduced_missing_ratio``: optional bounded ratio in
      ``[0.0, 1.0]``.
    - ``source_role``: optional bounded role label identifying which
      side of the join the column came from (``"left"`` / ``"right"``).
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ..., description="ColumnName of the column."
    )
    introduced_missing_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of missing values introduced by the join.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed after the join.",
    )
    introduced_missing_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded ratio of introduced missingness in [0.0, 1.0].",
    )
    source_role: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded role label identifying which side of the join the column came from.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _introduced_missing_count_does_not_exceed_total(self) -> "JoinIntroducedMissingness":
        if (
            self.introduced_missing_count is not None
            and self.total_count is not None
            and self.introduced_missing_count > self.total_count
        ):
            raise ValueError(
                "JoinIntroducedMissingness.introduced_missing_count must not "
                "exceed total_count."
            )
        return self


# ===========================================================================
# ModelExclusionSummary
# ===========================================================================
class ModelExclusionReason(str, Enum):
    """Stable codes for why a column was excluded from modeling.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The enum exists primarily as a convenience
    for reporting and audit; it is not exhaustive of every reason a
    quality stage may produce.
    """

    HIGH_MISSINGNESS = "high_missingness"
    CONSTANT_COLUMN = "constant_column"
    IDENTIFIER = "identifier"
    TARGET = "target"
    LEAKAGE_PRONE = "leakage_prone"
    USER_EXCLUDED = "user_excluded"
    DUPLICATE = "duplicate"
    NEAR_CONSTANT = "near_constant"
    OTHER = "other"


class ModelExclusionSummary(_QualityContractModel):
    """A typed per-column reason a column was excluded from modeling.

    The quality stage may flag columns that should not be used as model
    inputs (high missingness, identifiers, user-excluded, etc.). The
    exclusion is advisory — it does not block the pipeline by itself
    but is surfaced to modeling, validation, and reporting.

    Fields:

    - ``column_name``: :data:`ColumnName` of the excluded column.
    - ``reason``: :class:`ModelExclusionReason`.
    - ``detail``: optional bounded human-readable detail.
    - ``missing_ratio``: optional bounded ratio in ``[0.0, 1.0]``
      (relevant when ``reason`` is ``HIGH_MISSINGNESS``).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    column_name: ColumnName = Field(
        ..., description="ColumnName of the excluded column."
    )
    reason: ModelExclusionReason = Field(
        ..., description="ModelExclusionReason for the exclusion."
    )
    detail: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable detail.",
    )
    missing_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded missingness ratio in [0.0, 1.0].",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None


# ===========================================================================
# DataQualityIssue
# ===========================================================================
class DataQualityIssueKind(str, Enum):
    """Stable codes for typed data quality issues.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The enum is documentation-level; new issue
    kinds may be added in later tasks.
    """

    HIGH_MISSINGNESS = "high_missingness"
    CONSTANT_COLUMN = "constant_column"
    NEAR_CONSTANT_COLUMN = "near_constant_column"
    DUPLICATE_COLUMN = "duplicate_column"
    DUPLICATE_ROW = "duplicate_row"
    TYPE_MISMATCH = "type_mismatch"
    OUT_OF_RANGE = "out_of_range"
    INCONSISTENT_VALUE = "inconsistent_value"
    UNEXPECTED_NULL = "unexpected_null"
    OTHER = "other"


class DataQualityIssue(_QualityContractModel):
    """A typed data quality issue raised during stage 4.7.

    A data quality issue pairs a stable ``code`` / ``kind`` with a
    column or row locator and the bounded statistic that triggered the
    issue. It is intentionally limited to references and metadata so
    it can be safely embedded in :class:`DataQualityReport` without
    leaking raw data.

    Fields:

    - ``code``: stable machine-readable code (e.g.
      ``"COL_HIGH_MISSINGNESS"``).
    - ``kind``: :class:`DataQualityIssueKind`.
    - ``severity``: :class:`Severity` of the issue.
    - ``message``: human-readable message.
    - ``column_name``: optional :data:`ColumnName` the issue refers to.
    - ``observed_value``: optional bounded statistic the issue
      observed (e.g. ``"missing_ratio=0.42"``).
    - ``threshold``: optional bounded threshold (e.g. ``"0.1"``).
    - ``row_count_affected``: optional non-negative count of rows
      affected by the issue.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``context``: small bounded string-to-string metadata.
    """

    code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable issue code.",
    )
    kind: DataQualityIssueKind = Field(
        ...,
        description="DataQualityIssueKind classification.",
    )
    severity: Severity = Field(..., description="Severity of the issue.")
    message: str = Field(..., min_length=1, description="Human-readable issue message.")
    column_name: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName the issue refers to.",
    )
    observed_value: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded statistic the issue observed (e.g. 'missing_ratio=0.42').",
    )
    threshold: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded threshold (e.g. '0.1').",
    )
    row_count_affected: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of rows affected by the issue.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# MissingDataReport
# ===========================================================================
class MissingDataReport(_QualityContractModel):
    """A typed missing-data report for a dataset.

    A missing-data report bundles the per-column
    :class:`ColumnMissingness`, the per-row
    :class:`RowMissingnessSummary`, and the categorical
    :class:`MissingnessPatternSummary` into a single typed result. It
    must not embed raw dataframes, sample values, or backend objects.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the reported dataset.
    - ``column_missingness``: tuple of :class:`ColumnMissingness`
      (>= 1 when the dataset has >= 1 column; may be empty when the
      dataset has no columns).
    - ``row_summary``: optional :class:`RowMissingnessSummary`.
    - ``pattern_summary``: optional :class:`MissingnessPatternSummary`.
    - ``join_introduced_missingness``: optional tuple of
      :class:`JoinIntroducedMissingness` (populated only when this
      report describes a joined dataset).
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the reported dataset.",
    )
    column_missingness: tuple[ColumnMissingness, ...] = Field(
        default=(),
        description="Tuple of ColumnMissingness.",
    )
    row_summary: RowMissingnessSummary | None = Field(
        default=None,
        description="Optional RowMissingnessSummary.",
    )
    pattern_summary: MissingnessPatternSummary | None = Field(
        default=None,
        description="Optional MissingnessPatternSummary.",
    )
    join_introduced_missingness: tuple[JoinIntroducedMissingness, ...] = Field(
        default=(),
        description="Optional tuple of JoinIntroducedMissingness.",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of report computation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _column_missingness_names_unique(self) -> "MissingDataReport":
        seen: set[str] = set()
        for cm in self.column_missingness:
            if cm.column_name in seen:
                raise ValueError(
                    f"MissingDataReport.column_missingness has duplicate "
                    f"column names: {cm.column_name!r}."
                )
            seen.add(cm.column_name)
        return self

    @model_validator(mode="after")
    def _join_introduced_missingness_names_unique(self) -> "MissingDataReport":
        seen: set[str] = set()
        for jm in self.join_introduced_missingness:
            if jm.column_name in seen:
                raise ValueError(
                    f"MissingDataReport.join_introduced_missingness has duplicate "
                    f"column names: {jm.column_name!r}."
                )
            seen.add(jm.column_name)
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "MissingDataReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self


# ===========================================================================
# DataQualityReport
# ===========================================================================
class DataQualityReport(_QualityContractModel):
    """The typed output of stage 4.7 (data quality and missingness).

    A data quality report is the bundle that downstream consumers
    (profiling, joins, features, modeling, validation, reporting)
    consume. It pairs a :class:`MissingDataReport` with the broader
    :class:`DataQualityIssue` collection, the
    :class:`ModelExclusionSummary` advisories, and a few convenience
    summary fields.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the reported dataset.
    - ``missing_data``: :class:`MissingDataReport` for the dataset.
    - ``quality_issues``: tuple of :class:`DataQualityIssue`.
    - ``model_exclusions``: tuple of :class:`ModelExclusionSummary`.
    - ``has_target_associated_missingness``: optional flag indicating
      that target-associated columns have severe missingness. When
      ``True``, the validation stage may downgrade associational
      outputs to ``unsupported`` (see interface-map stage 4.7).
    - ``is_passthrough_clean``: optional flag indicating the dataset
      passed the documented quality thresholds.
    - ``issues`` / ``warnings``: common typed issue/warning collections.
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the reported dataset.",
    )
    missing_data: MissingDataReport = Field(
        ...,
        description="MissingDataReport for the dataset.",
    )
    quality_issues: tuple[DataQualityIssue, ...] = Field(
        default=(),
        description="Tuple of DataQualityIssue (immutable).",
    )
    model_exclusions: tuple[ModelExclusionSummary, ...] = Field(
        default=(),
        description="Tuple of ModelExclusionSummary (immutable).",
    )
    has_target_associated_missingness: bool | None = Field(
        default=None,
        description=(
            "Optional flag indicating target-associated columns have severe "
            "missingness. When True, validation may downgrade associational "
            "outputs to 'unsupported'."
        ),
    )
    is_passthrough_clean: bool | None = Field(
        default=None,
        description="Optional flag indicating the dataset passed documented quality thresholds.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during quality analysis (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during quality analysis (immutable).",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of report computation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _model_exclusion_column_names_unique(self) -> "DataQualityReport":
        seen: set[str] = set()
        for excl in self.model_exclusions:
            if excl.column_name in seen:
                raise ValueError(
                    f"DataQualityReport.model_exclusions has duplicate "
                    f"column names: {excl.column_name!r}."
                )
            seen.add(excl.column_name)
        return self

    @model_validator(mode="after")
    def _passthrough_clean_consistent_with_issues(self) -> "DataQualityReport":
        if self.is_passthrough_clean is True:
            # A "passthrough clean" report must not have ERROR/CRITICAL
            # issues (warnings are allowed).
            for issue in self.quality_issues:
                if issue.severity in (Severity.ERROR, Severity.CRITICAL):
                    raise ValueError(
                        "DataQualityReport with is_passthrough_clean=True "
                        "must not contain ERROR-or-higher quality_issues."
                    )
            for issue in self.issues:
                if issue.severity in (Severity.ERROR, Severity.CRITICAL):
                    raise ValueError(
                        "DataQualityReport with is_passthrough_clean=True "
                        "must not contain ERROR-or-higher common issues."
                    )
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "DataQualityReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self
