"""Profiling contracts (Build Queue v2.1 Task 25).

Public contracts for the ``profiling`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Profiling contracts describe
the typed output of stage 4.8 (distribution profiling): distribution
summaries, quantile estimates, frequency tables, missingness /
cardinality / duplicate / outlier summaries, and the typed warnings
raised during profiling. They are dependency-light and never embed raw
dataframes, file bytes, sample values, or backend objects.

Per the interface map (stage 4.8), large datasets use an *approximate*
mode; the profile records ``computation_mode`` (exact vs approximate)
and ``approximation_method`` so consumers can decide how much to trust
each summary. The profiling stage never produces analytical claims.

Scope:

- Enums: ``ProfileComputationMode``, ``ProfileApproximationMethod``,
  ``OutlierDetectionMethod``.
- Specs and request/result: ``ProfilingSpec``, ``ProfilingRequest``,
  ``DatasetProfile``, ``ColumnProfile``.
- Per-column summaries: ``NumericProfile``, ``CategoricalProfile``,
  ``DatetimeProfile``, ``MissingnessProfile``, ``CardinalityProfile``,
  ``DuplicateProfile``, ``OutlierProfile``.
- Distribution primitives: ``DistributionSummary``,
  ``QuantileSummary``, ``FrequencySummary``.
- Typed warnings: ``ConstantColumnWarning``,
  ``HighCardinalityWarning``.

Not implemented here: actual profiling logic. The profiling stage is
deferred to later implementation tasks and must consume these
contracts only.
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
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.schemas import ColumnName, LogicalDataType

__all__ = [
    # Enums
    "ProfileComputationMode",
    "ProfileApproximationMethod",
    "OutlierDetectionMethod",
    # Specs and request/result
    "ProfilingSpec",
    "ProfilingRequest",
    "DatasetProfile",
    "ColumnProfile",
    # Per-column summaries
    "NumericProfile",
    "CategoricalProfile",
    "DatetimeProfile",
    "MissingnessProfile",
    "CardinalityProfile",
    "DuplicateProfile",
    "OutlierProfile",
    # Distribution primitives
    "DistributionSummary",
    "QuantileSummary",
    "FrequencySummary",
    # Typed warnings
    "ConstantColumnWarning",
    "HighCardinalityWarning",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ProfilingContractModel(BaseModel):
    """Base configuration for profiling contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, file bytes,
    sample values, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for missingness / outlier /
# duplicate fractions.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]
# Bounded ratio in (0.0, 1.0] used for quantiles. Open at 0 because a
# zero-quantile is meaningless; closed at 1 because a 100th-percentile
# is well-defined.
_QuantileRatio = Annotated[float, Field(gt=0.0, le=1.0)]


# ===========================================================================
# Enums
# ===========================================================================
class ProfileComputationMode(str, Enum):
    """Whether a profile was computed exactly or approximately.

    Per the interface map (stage 4.8), large datasets use an approximate
    mode; ``computation_mode`` records that decision so downstream
    consumers can decide how much to trust the profile.
    """

    EXACT = "exact"
    APPROXIMATE = "approximate"
    HYBRID = "hybrid"


class ProfileApproximationMethod(str, Enum):
    """How an approximate profile was computed.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The enum is documentation-level; new methods
    may be added in later tasks.
    """

    RESERVOIR_SAMPLING = "reservoir_sampling"
    T_DIGEST = "t_digest"
    KLL = "kll"
    HLL = "hll"
    EXACT = "exact"  # only valid when computation_mode == EXACT
    UNKNOWN = "unknown"


class OutlierDetectionMethod(str, Enum):
    """How outliers were detected in a column.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``NONE`` is reserved for profiles that did
    not run an outlier pass.
    """

    IQR = "iqr"
    ZSCORE = "zscore"
    MAD = "mad"
    ISOLATION_FOREST = "isolation_forest"
    NONE = "none"
    UNKNOWN = "unknown"


# ===========================================================================
# Distribution primitives
# ===========================================================================
class QuantileSummary(_ProfilingContractModel):
    """A bounded list of quantile estimates for a numeric column.

    Quantiles are stored as a list of ``(quantile, value)`` pairs in
    strictly-increasing quantile order, with quantile in ``(0.0, 1.0]``
    and value a real number. The contract does not pin a particular
    algorithm; ``profiling_method`` records which algorithm produced
    the estimates.

    Fields:

    - ``quantile_pairs``: tuple of ``(quantile, value)`` pairs. At
      least one pair is required.
    - ``profiling_method``: optional bounded method label
      (``"exact"`` / ``"t_digest"`` / ``"kll"`` etc.).
    - ``notes``: optional bounded human-readable note.
    """

    quantile_pairs: tuple[tuple[float, float], ...] = Field(
        ...,
        min_length=1,
        description="Tuple of (quantile, value) pairs.",
    )
    profiling_method: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded method label.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _quantiles_strictly_increasing_in_unit_interval(self) -> "QuantileSummary":
        last: float | None = None
        for q, v in self.quantile_pairs:
            if not (0.0 < q <= 1.0):
                raise ValueError(
                    "QuantileSummary quantiles must be in (0.0, 1.0]."
                )
            if last is not None and q <= last:
                raise ValueError(
                    "QuantileSummary quantile_pairs must be strictly increasing in quantile order."
                )
            last = q
            # ``v`` is intentionally not bounded — the contract is
            # generic over any numeric column.
            del v
        return self


class FrequencySummary(_ProfilingContractModel):
    """A bounded ``(value, count)`` frequency table for a column.

    A frequency summary is a discovery aid for downstream consumers
    (categorical profiling, association diagnostics, reporting). It is
    intentionally limited to ``max_entries`` records so that very
    high-cardinality columns do not bloat the profile.

    Fields:

    - ``entries``: tuple of ``(value, count)`` pairs in deterministic
      insertion order.
    - ``total_count``: optional non-negative total count of values
      that produced the table.
    - ``truncated``: ``True`` when more than ``max_entries`` distinct
      values were observed and only the top-``max_entries`` are
      recorded. ``False`` when the table is complete.
    - ``max_entries``: optional non-negative upper bound on the
      number of entries recorded. Defaults to 0 (unbounded).
    - ``notes``: optional bounded human-readable note.
    """

    entries: tuple[tuple[str, int], ...] = Field(
        default=(),
        description="Tuple of (value, count) pairs.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative total count of values that produced the table.",
    )
    truncated: bool = Field(
        default=False,
        description="True when more than max_entries distinct values were observed.",
    )
    max_entries: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of entries recorded.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _negative_counts_rejected(self) -> "FrequencySummary":
        for _value, count in self.entries:
            if count < 0:
                raise ValueError(
                    "FrequencySummary entry counts must be non-negative."
                )
        if self.total_count is not None and self.total_count < 0:
            raise ValueError(
                "FrequencySummary.total_count must be non-negative."
            )
        return self

    @model_validator(mode="after")
    def _truncated_consistent_with_max_entries(self) -> "FrequencySummary":
        if (
            self.truncated
            and self.max_entries is not None
            and len(self.entries) < self.max_entries
        ):
            raise ValueError(
                "FrequencySummary truncated=True with max_entries set requires "
                "at least max_entries entries."
            )
        return self


class DistributionSummary(_ProfilingContractModel):
    """A typed distribution summary for a single numeric column.

    A distribution summary bundles the basic numeric descriptors
    (``min``, ``max``, ``mean``, ``stddev``), the bounded
    :class:`QuantileSummary`, and a few optional convenience fields.
    It must not embed raw samples or histograms.

    Fields:

    - ``min`` / ``max``: optional real-number bounds.
    - ``mean`` / ``stddev``: optional real-number central-tendency
      statistics. ``stddev`` must be ``>= 0`` when provided.
    - ``quantiles``: optional :class:`QuantileSummary`.
    - ``is_bounded``: optional flag indicating the column has a known
      finite support (e.g. an enum).
    - ``profiling_method``: optional bounded method label.
    - ``notes``: optional bounded human-readable note.
    """

    min: float | None = Field(
        default=None,
        description="Optional real-number minimum observed value.",
    )
    max: float | None = Field(
        default=None,
        description="Optional real-number maximum observed value.",
    )
    mean: float | None = Field(
        default=None,
        description="Optional real-number mean observed value.",
    )
    stddev: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative real-number standard deviation.",
    )
    quantiles: QuantileSummary | None = Field(
        default=None,
        description="Optional bounded QuantileSummary.",
    )
    is_bounded: bool | None = Field(
        default=None,
        description="Optional flag indicating the column has a known finite support.",
    )
    profiling_method: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded method label.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _min_max_consistent(self) -> "DistributionSummary":
        if (
            self.min is not None
            and self.max is not None
            and self.max < self.min
        ):
            raise ValueError(
                "DistributionSummary.max must be >= min."
            )
        return self


# ===========================================================================
# Per-column summaries
# ===========================================================================
class NumericProfile(_ProfilingContractModel):
    """Numeric-column profile summary.

    A numeric profile captures the bounded :class:`DistributionSummary`
    and a small set of optional auxiliary statistics. It must not embed
    raw samples, histograms, or model objects.

    Fields:

    - ``distribution``: :class:`DistributionSummary` for the column.
    - ``zero_count`` / ``negative_count`` / ``positive_count``:
      optional non-negative counts of values with that sign.
    - ``mean_abs``: optional non-negative mean of absolute values.
    - ``coefficient_of_variation``: optional non-negative coefficient
      of variation (``|stddev / mean|`` when ``mean != 0``).
    """

    distribution: DistributionSummary = Field(
        ...,
        description="DistributionSummary for the column.",
    )
    zero_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of zero values.",
    )
    negative_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of negative values.",
    )
    positive_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of positive values.",
    )
    mean_abs: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative mean of absolute values.",
    )
    coefficient_of_variation: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative coefficient of variation.",
    )


class CategoricalProfile(_ProfilingContractModel):
    """Categorical-column profile summary.

    A categorical profile captures the bounded
    :class:`FrequencySummary` plus a small set of optional
    statistics.

    Fields:

    - ``top_frequencies``: optional :class:`FrequencySummary` of the
      most-frequent values.
    - ``distinct_count``: optional non-negative count of distinct
      observed values.
    - ``most_frequent_value``: optional bounded most-frequent value
      label.
    - ``most_frequent_count``: optional non-negative count of the
      most-frequent value.
    - ``least_frequent_count``: optional non-negative count of the
      least-frequent value.
    """

    top_frequencies: FrequencySummary | None = Field(
        default=None,
        description="Optional FrequencySummary of the most-frequent values.",
    )
    distinct_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of distinct observed values.",
    )
    most_frequent_value: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded most-frequent value label.",
    )
    most_frequent_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of the most-frequent value.",
    )
    least_frequent_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of the least-frequent value.",
    )

    @model_validator(mode="after")
    def _most_frequent_pair_consistent(self) -> "CategoricalProfile":
        if (
            self.most_frequent_value is not None
            and self.most_frequent_count is None
        ) or (
            self.most_frequent_value is None
            and self.most_frequent_count is not None
        ):
            raise ValueError(
                "CategoricalProfile.most_frequent_value and most_frequent_count "
                "must be provided together."
            )
        return self


class DatetimeProfile(_ProfilingContractModel):
    """Datetime-column profile summary.

    A datetime profile captures the bounded
    ``min``/``max``/``distinct_count`` and an optional bucketed
    frequency summary. It must not embed raw datetimes, sample
    values, or histograms.

    Fields:

    - ``min`` / ``max``: optional timezone-aware datetimes.
    - ``distinct_count``: optional non-negative count of distinct
      observed values.
    - ``bucket_frequencies``: optional :class:`FrequencySummary` of
      bucketed counts (e.g. year-bucketed).
    - ``bucket_label``: optional bounded label describing the bucket
      scheme (``"year"`` / ``"month"`` / ``"day"`` / etc.).
    """

    min: datetime | None = Field(
        default=None,
        description="Optional timezone-aware minimum observed datetime.",
    )
    max: datetime | None = Field(
        default=None,
        description="Optional timezone-aware maximum observed datetime.",
    )
    distinct_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of distinct observed datetimes.",
    )
    bucket_frequencies: FrequencySummary | None = Field(
        default=None,
        description="Optional FrequencySummary of bucketed counts.",
    )
    bucket_label: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded label describing the bucket scheme.",
    )

    @model_validator(mode="after")
    def _min_max_aware_and_ordered(self) -> "DatetimeProfile":
        if self.min is not None and self.min.tzinfo is None:
            object.__setattr__(
                self, "min", self.min.replace(tzinfo=timezone.utc)
            )
        if self.max is not None and self.max.tzinfo is None:
            object.__setattr__(
                self, "max", self.max.replace(tzinfo=timezone.utc)
            )
        if (
            self.min is not None
            and self.max is not None
            and self.max < self.min
        ):
            raise ValueError(
                "DatetimeProfile.max must be >= min."
            )
        return self


class MissingnessProfile(_ProfilingContractModel):
    """Missingness summary for a single column.

    A missingness profile records the bounded missing ratio plus
    optional auxiliary signals (e.g. "missing is a signal" flags).

    Fields:

    - ``missing_count`` / ``total_count``: optional non-negative
      counts.
    - ``missing_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``missing_is_signal``: optional flag indicating that missingness
      is a meaningful signal in the column.
    """

    missing_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of missing values.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed.",
    )
    missing_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded missingness ratio in [0.0, 1.0].",
    )
    missing_is_signal: bool | None = Field(
        default=None,
        description="Optional flag indicating that missingness is a meaningful signal.",
    )

    @model_validator(mode="after")
    def _missing_count_does_not_exceed_total(self) -> "MissingnessProfile":
        if (
            self.missing_count is not None
            and self.total_count is not None
            and self.missing_count > self.total_count
        ):
            raise ValueError(
                "MissingnessProfile.missing_count must not exceed total_count."
            )
        return self


class CardinalityProfile(_ProfilingContractModel):
    """Cardinality summary for a single column.

    A cardinality profile reports the bounded distinct count plus
    optional signals (e.g. high-cardinality warnings).

    Fields:

    - ``distinct_count``: optional non-negative count of distinct
      observed values.
    - ``total_count``: optional non-negative count of total values
      observed.
    - ``distinct_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``is_high_cardinality``: optional flag indicating the column
      exceeds the documented high-cardinality threshold.
    """

    distinct_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of distinct observed values.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed.",
    )
    distinct_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded distinct ratio in [0.0, 1.0].",
    )
    is_high_cardinality: bool | None = Field(
        default=None,
        description="Optional flag indicating the column exceeds the high-cardinality threshold.",
    )


class DuplicateProfile(_ProfilingContractModel):
    """Duplicate-row or duplicate-key summary for a single column.

    A duplicate profile records the bounded count of duplicate rows
    in a single column, or the count of duplicate ``(column)`` keys
    when used as a join key. It must not embed raw duplicate values.

    Fields:

    - ``duplicate_count``: optional non-negative count of duplicate
      values (occurrences beyond the first).
    - ``total_count``: optional non-negative count of total values
      observed.
    - ``duplicate_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``is_unique_key``: optional flag indicating the column has no
      duplicate values (and is therefore a unique key candidate).
    """

    duplicate_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of duplicate values.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed.",
    )
    duplicate_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded duplicate ratio in [0.0, 1.0].",
    )
    is_unique_key: bool | None = Field(
        default=None,
        description="Optional flag indicating the column has no duplicate values.",
    )

    @model_validator(mode="after")
    def _duplicate_count_does_not_exceed_total(self) -> "DuplicateProfile":
        if (
            self.duplicate_count is not None
            and self.total_count is not None
            and self.duplicate_count > self.total_count
        ):
            raise ValueError(
                "DuplicateProfile.duplicate_count must not exceed total_count."
            )
        return self


class OutlierProfile(_ProfilingContractModel):
    """Outlier summary for a single column.

    An outlier profile records the bounded outlier count, ratio, and
    the method used to detect outliers. ``method == NONE`` means
    outlier detection was not run (the bounded counts are all
    ``None`` in that case).

    Fields:

    - ``outlier_count``: optional non-negative count of outliers.
    - ``total_count``: optional non-negative count of total values
      observed.
    - ``outlier_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``method``: :class:`OutlierDetectionMethod` used (defaults to
      ``NONE``).
    - ``lower_bound`` / ``upper_bound``: optional real-number bounds
      outside of which a value is considered an outlier. ``None`` for
      non-numeric columns or when the method does not produce a bound.
    - ``profiling_method``: optional bounded method label.
    """

    outlier_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of outliers.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed.",
    )
    outlier_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded outlier ratio in [0.0, 1.0].",
    )
    method: OutlierDetectionMethod = Field(
        default=OutlierDetectionMethod.NONE,
        description="OutlierDetectionMethod used. Defaults to NONE.",
    )
    lower_bound: float | None = Field(
        default=None,
        description="Optional real-number lower bound outside of which a value is an outlier.",
    )
    upper_bound: float | None = Field(
        default=None,
        description="Optional real-number upper bound outside of which a value is an outlier.",
    )
    profiling_method: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded method label.",
    )

    @model_validator(mode="after")
    def _outlier_count_does_not_exceed_total(self) -> "OutlierProfile":
        if (
            self.outlier_count is not None
            and self.total_count is not None
            and self.outlier_count > self.total_count
        ):
            raise ValueError(
                "OutlierProfile.outlier_count must not exceed total_count."
            )
        return self

    @model_validator(mode="after")
    def _bounds_consistent(self) -> "OutlierProfile":
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.upper_bound < self.lower_bound
        ):
            raise ValueError(
                "OutlierProfile.upper_bound must be >= lower_bound."
            )
        return self

    @model_validator(mode="after")
    def _method_none_implies_no_counts(self) -> "OutlierProfile":
        if self.method is OutlierDetectionMethod.NONE:
            if (
                self.outlier_count is not None
                or self.total_count is not None
                or self.outlier_ratio is not None
                or self.lower_bound is not None
                or self.upper_bound is not None
            ):
                raise ValueError(
                    "OutlierProfile with method=NONE must not include "
                    "outlier_count, total_count, outlier_ratio, lower_bound, "
                    "or upper_bound."
                )
        return self


# ===========================================================================
# ColumnProfile
# ===========================================================================
class ColumnProfile(_ProfilingContractModel):
    """The full profile for a single column.

    A column profile bundles the per-logical-type summaries
    (numeric, categorical, datetime), the missingness / cardinality /
    duplicate / outlier summaries, and a few convenience flags. Only
    the summaries that match the column's logical type are
    meaningful; the others should be ``None``.

    Fields:

    - ``column_name``: :data:`ColumnName` of the profiled column.
    - ``logical_type``: optional :class:`LogicalDataType` of the
      column. Used to interpret the per-type summaries.
    - ``computation_mode``: :class:`ProfileComputationMode` used for
      this column.
    - ``approximation_method``: optional
      :class:`ProfileApproximationMethod` (required when
      ``computation_mode == APPROXIMATE``).
    - ``numeric`` / ``categorical`` / ``datetime``: optional per-type
      summaries.
    - ``missingness``: optional :class:`MissingnessProfile`.
    - ``cardinality``: optional :class:`CardinalityProfile`.
    - ``duplicates``: optional :class:`DuplicateProfile`.
    - ``outliers``: optional :class:`OutlierProfile`.
    - ``sample_size``: optional non-negative number of rows sampled
      to compute this profile (only when ``computation_mode ==
      APPROXIMATE``).
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the profiled column.",
    )
    logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional LogicalDataType of the column.",
    )
    computation_mode: ProfileComputationMode = Field(
        default=ProfileComputationMode.EXACT,
        description="ProfileComputationMode used for this column.",
    )
    approximation_method: ProfileApproximationMethod | None = Field(
        default=None,
        description="Optional ProfileApproximationMethod (required when computation_mode == APPROXIMATE).",
    )
    numeric: NumericProfile | None = Field(
        default=None,
        description="Optional NumericProfile (meaningful for numeric columns).",
    )
    categorical: CategoricalProfile | None = Field(
        default=None,
        description="Optional CategoricalProfile (meaningful for categorical columns).",
    )
    datetime: DatetimeProfile | None = Field(
        default=None,
        description="Optional DatetimeProfile (meaningful for datetime columns).",
    )
    missingness: MissingnessProfile | None = Field(
        default=None,
        description="Optional MissingnessProfile.",
    )
    cardinality: CardinalityProfile | None = Field(
        default=None,
        description="Optional CardinalityProfile.",
    )
    duplicates: DuplicateProfile | None = Field(
        default=None,
        description="Optional DuplicateProfile.",
    )
    outliers: OutlierProfile | None = Field(
        default=None,
        description="Optional OutlierProfile.",
    )
    sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative number of rows sampled (for APPROXIMATE mode).",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _approximation_method_consistent(self) -> "ColumnProfile":
        if self.computation_mode is ProfileComputationMode.APPROXIMATE:
            if self.approximation_method is None:
                raise ValueError(
                    "ColumnProfile with computation_mode=APPROXIMATE must "
                    "include an approximation_method."
                )
            if self.approximation_method is ProfileApproximationMethod.EXACT:
                raise ValueError(
                    "ColumnProfile with computation_mode=APPROXIMATE must "
                    "not have approximation_method=EXACT."
                )
        return self

    @model_validator(mode="after")
    def _exact_mode_forbids_sample_size(self) -> "ColumnProfile":
        if (
            self.computation_mode is ProfileComputationMode.EXACT
            and self.sample_size is not None
        ):
            raise ValueError(
                "ColumnProfile with computation_mode=EXACT must not include "
                "sample_size."
            )
        return self


# ===========================================================================
# Typed warnings
# ===========================================================================
class ConstantColumnWarning(_ProfilingContractModel):
    """A typed warning raised when a column is constant (single value).

    A constant-column warning is recorded when the column has only
    one distinct non-null value. The warning is advisory — it does
    not block the pipeline.

    Fields:

    - ``column_name``: :data:`ColumnName` of the constant column.
    - ``value``: optional bounded observed constant value
      (serialized as a string).
    - ``row_count``: optional non-negative count of non-null values
      observed.
    - ``severity``: :class:`Severity` of the warning.
    - ``code`` / ``message``: optional bounded metadata.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the constant column.",
    )
    value: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded observed constant value (serialized as a string).",
    )
    row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of non-null values observed.",
    )
    severity: Severity = Field(
        default=Severity.WARNING,
        description="Severity of the warning. Defaults to WARNING.",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional bounded machine-readable code.",
    )
    message: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional human-readable message.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None


class HighCardinalityWarning(_ProfilingContractModel):
    """A typed warning raised when a column is high-cardinality.

    A high-cardinality warning is recorded when the column's
    distinct ratio exceeds the documented threshold. The warning is
    advisory — it does not block the pipeline.

    Fields:

    - ``column_name``: :data:`ColumnName` of the high-cardinality
      column.
    - ``distinct_count``: optional non-negative count of distinct
      values.
    - ``total_count``: optional non-negative count of total values
      observed.
    - ``distinct_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``threshold_ratio``: optional bounded threshold ratio in
      ``[0.0, 1.0]`` the column exceeded.
    - ``severity``: :class:`Severity` of the warning.
    - ``code`` / ``message``: optional bounded metadata.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the high-cardinality column.",
    )
    distinct_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of distinct values.",
    )
    total_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total values observed.",
    )
    distinct_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded distinct ratio in [0.0, 1.0].",
    )
    threshold_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded threshold ratio the column exceeded.",
    )
    severity: Severity = Field(
        default=Severity.WARNING,
        description="Severity of the warning. Defaults to WARNING.",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional bounded machine-readable code.",
    )
    message: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional human-readable message.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None


# ===========================================================================
# ProfilingSpec
# ===========================================================================
class ProfilingSpec(_ProfilingContractModel):
    """A bounded spec describing what the profiling stage should compute.

    A profiling spec is a small, typed set of flags that downstream
    consumers (profiling, reporting) can use to opt in / out of
    specific summaries. The contract intentionally has no
    ``must_compute_everything`` flag — consumers should opt in
    explicitly.

    Fields:

    - ``compute_numeric``: include ``NumericProfile`` summaries.
    - ``compute_categorical``: include ``CategoricalProfile``
      summaries.
    - ``compute_datetime``: include ``DatetimeProfile`` summaries.
    - ``compute_missingness``: include ``MissingnessProfile``
      summaries.
    - ``compute_cardinality``: include ``CardinalityProfile``
      summaries.
    - ``compute_duplicates``: include ``DuplicateProfile`` summaries.
    - ``compute_outliers``: include ``OutlierProfile`` summaries.
    - ``outlier_method``: optional :class:`OutlierDetectionMethod`.
    - ``frequency_top_k``: optional non-negative upper bound on
      ``FrequencySummary`` entries.
    - ``max_quantiles``: optional non-negative upper bound on
      ``QuantileSummary`` pairs.
    - ``approximate_above_row_count``: optional non-negative row
      count threshold above which ``computation_mode`` is forced to
      ``APPROXIMATE``. ``None`` means "always exact".
    """

    compute_numeric: bool = Field(
        default=True, description="Include NumericProfile summaries."
    )
    compute_categorical: bool = Field(
        default=True, description="Include CategoricalProfile summaries."
    )
    compute_datetime: bool = Field(
        default=True, description="Include DatetimeProfile summaries."
    )
    compute_missingness: bool = Field(
        default=True, description="Include MissingnessProfile summaries."
    )
    compute_cardinality: bool = Field(
        default=True, description="Include CardinalityProfile summaries."
    )
    compute_duplicates: bool = Field(
        default=False, description="Include DuplicateProfile summaries."
    )
    compute_outliers: bool = Field(
        default=False, description="Include OutlierProfile summaries."
    )
    outlier_method: OutlierDetectionMethod | None = Field(
        default=None,
        description="Optional OutlierDetectionMethod (required when compute_outliers=True).",
    )
    frequency_top_k: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on FrequencySummary entries.",
    )
    max_quantiles: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on QuantileSummary pairs.",
    )
    approximate_above_row_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Optional non-negative row-count threshold above which "
            "computation_mode is forced to APPROXIMATE."
        ),
    )

    @model_validator(mode="after")
    def _outlier_method_consistent(self) -> "ProfilingSpec":
        if self.compute_outliers and self.outlier_method is None:
            raise ValueError(
                "ProfilingSpec with compute_outliers=True must include an outlier_method."
            )
        if not self.compute_outliers and self.outlier_method is not None:
            raise ValueError(
                "ProfilingSpec with compute_outliers=False must not include an outlier_method."
            )
        return self


# ===========================================================================
# ProfilingRequest
# ===========================================================================
class ProfilingRequest(_ProfilingContractModel):
    """A typed request to profile a dataset.

    A profiling request takes a :class:`DatasetHandle`, an
    :class:`ProfilingSpec`, the :class:`ExecutionLimitPolicy` to
    apply, and a few optional hints. It must not reference raw
    dataframes, file bytes, or backend objects.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the dataset to profile.
    - ``spec``: :class:`ProfilingSpec` (defaults to a spec with all
      common compute flags on).
    - ``execution_limits``: :class:`ExecutionLimitPolicy` to apply
      (row, column, collect, conversion, memory budgets).
    - ``min_sample_size`` / ``max_sample_size``: optional
      non-negative bounds for sampling (only used in ``APPROXIMATE``
      mode).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the dataset to profile.",
    )
    spec: ProfilingSpec = Field(
        default_factory=ProfilingSpec,
        description="ProfilingSpec describing what to compute.",
    )
    execution_limits: ExecutionLimitPolicy = Field(
        ...,
        description="ExecutionLimitPolicy to apply during profiling.",
    )
    min_sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative minimum sample size for APPROXIMATE mode.",
    )
    max_sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative maximum sample size for APPROXIMATE mode.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _sample_size_bounds_consistent(self) -> "ProfilingRequest":
        if (
            self.min_sample_size is not None
            and self.max_sample_size is not None
            and self.max_sample_size < self.min_sample_size
        ):
            raise ValueError(
                "ProfilingRequest.max_sample_size must be >= min_sample_size."
            )
        return self


# ===========================================================================
# DatasetProfile
# ===========================================================================
class DatasetProfile(_ProfilingContractModel):
    """The typed output of stage 4.8 (distribution profiling).

    A dataset profile is the bundle that downstream consumers
    (associations, joins, reporting) consume. It pairs a
    per-column :class:`ColumnProfile` with the typed warnings raised
    during profiling and a few convenience summary fields.

    Per the interface map (stage 4.8), the profile records
    ``computation_mode`` and ``approximation_method`` so consumers
    can decide how much to trust each summary. The profiling stage
    never produces analytical claims.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the profiled dataset.
    - ``computation_mode``: :class:`ProfileComputationMode` (defaults
      to ``EXACT``).
    - ``approximation_method``: optional
      :class:`ProfileApproximationMethod` (required when
      ``computation_mode == APPROXIMATE``).
    - ``column_profiles``: tuple of :class:`ColumnProfile` (>= 1
      when the dataset has >= 1 column; may be empty when the dataset
      has no columns).
    - ``row_count_estimate``: optional non-negative row-count
      estimate.
    - ``constant_column_warnings``: tuple of
      :class:`ConstantColumnWarning` (immutable).
    - ``high_cardinality_warnings``: tuple of
      :class:`HighCardinalityWarning` (immutable).
    - ``issues`` / ``warnings``: common typed issue/warning
      collections.
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the profiled dataset.",
    )
    computation_mode: ProfileComputationMode = Field(
        default=ProfileComputationMode.EXACT,
        description="ProfileComputationMode used for the dataset.",
    )
    approximation_method: ProfileApproximationMethod | None = Field(
        default=None,
        description="Optional ProfileApproximationMethod (required when computation_mode == APPROXIMATE).",
    )
    column_profiles: tuple[ColumnProfile, ...] = Field(
        default=(),
        description="Tuple of ColumnProfile.",
    )
    row_count_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row-count estimate.",
    )
    constant_column_warnings: tuple[ConstantColumnWarning, ...] = Field(
        default=(),
        description="Tuple of ConstantColumnWarning (immutable).",
    )
    high_cardinality_warnings: tuple[HighCardinalityWarning, ...] = Field(
        default=(),
        description="Tuple of HighCardinalityWarning (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during profiling (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during profiling (immutable).",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of profile computation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _approximation_method_consistent(self) -> "DatasetProfile":
        if self.computation_mode is ProfileComputationMode.APPROXIMATE:
            if self.approximation_method is None:
                raise ValueError(
                    "DatasetProfile with computation_mode=APPROXIMATE must "
                    "include an approximation_method."
                )
            if self.approximation_method is ProfileApproximationMethod.EXACT:
                raise ValueError(
                    "DatasetProfile with computation_mode=APPROXIMATE must "
                    "not have approximation_method=EXACT."
                )
        return self

    @model_validator(mode="after")
    def _column_profile_names_unique(self) -> "DatasetProfile":
        seen: set[str] = set()
        for cp in self.column_profiles:
            if cp.column_name in seen:
                raise ValueError(
                    f"DatasetProfile.column_profiles has duplicate column names: {cp.column_name!r}."
                )
            seen.add(cp.column_name)
        return self

    @model_validator(mode="after")
    def _constant_column_warnings_unique(self) -> "DatasetProfile":
        seen: set[str] = set()
        for w in self.constant_column_warnings:
            if w.column_name in seen:
                raise ValueError(
                    f"DatasetProfile.constant_column_warnings has duplicate column names: {w.column_name!r}."
                )
            seen.add(w.column_name)
        return self

    @model_validator(mode="after")
    def _high_cardinality_warnings_unique(self) -> "DatasetProfile":
        seen: set[str] = set()
        for w in self.high_cardinality_warnings:
            if w.column_name in seen:
                raise ValueError(
                    f"DatasetProfile.high_cardinality_warnings has duplicate column names: {w.column_name!r}."
                )
            seen.add(w.column_name)
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "DatasetProfile":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self
