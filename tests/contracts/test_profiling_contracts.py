"""Tests for profiling contracts (Build Queue v2.1 Task 25).

Covers:

- Enums: ``ProfileComputationMode`` / ``ProfileApproximationMethod``
  / ``OutlierDetectionMethod`` valid/invalid values.
- Distribution primitives: ``QuantileSummary`` (strictly-increasing
  quantiles in (0.0, 1.0]), ``FrequencySummary`` (truncation
  consistency), ``DistributionSummary`` (min/max consistency,
  non-negative stddev).
- Per-column summaries: ``NumericProfile``,
  ``CategoricalProfile`` (most-frequent pair consistency),
  ``DatetimeProfile`` (timezone coercion, min/max ordering),
  ``MissingnessProfile`` / ``CardinalityProfile`` /
  ``DuplicateProfile`` (count <= total invariants),
  ``OutlierProfile`` (method=NONE implies no counts).
- ``ColumnProfile`` invariants: APPROXIMATE requires
  ``approximation_method`` (and forbids ``EXACT``); EXACT forbids
  ``sample_size``.
- Typed warnings: ``ConstantColumnWarning`` and
  ``HighCardinalityWarning``.
- ``ProfilingSpec`` invariants: ``compute_outliers=True`` requires
  ``outlier_method``; ``compute_outliers=False`` forbids it.
- ``ProfilingRequest`` invariants: ``max_sample_size >=
  min_sample_size``.
- ``DatasetProfile`` invariants: unique column / warning column
  names; APPROXIMATE requires ``approximation_method``;
  ``computed_at`` coerced to UTC.

These tests intentionally avoid importing any heavy compute library so
that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)
from analytics_platform.contracts.profiling import (
    CardinalityProfile,
    CategoricalProfile,
    ColumnProfile,
    ConstantColumnWarning,
    DatasetProfile,
    DatetimeProfile,
    DistributionSummary,
    DuplicateProfile,
    FrequencySummary,
    HighCardinalityWarning,
    MissingnessProfile,
    NumericProfile,
    OutlierDetectionMethod,
    OutlierProfile,
    ProfileApproximationMethod,
    ProfileComputationMode,
    ProfilingRequest,
    ProfilingSpec,
    QuantileSummary,
)
from analytics_platform.contracts.schemas import LogicalDataType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle(name: str = "orders") -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name=name)


def _default_execution_limits() -> ExecutionLimitPolicy:
    return ExecutionLimitPolicy(
        collect=CollectPolicy(mode=CollectMode.BOUNDED, max_rows=10_000),
        pandas_conversion=PandasConversionPolicy(
            mode=PandasConversionMode.BOUNDED,
            max_rows=10_000,
        ),
        memory_budget=MemoryBudgetPolicy(max_bytes=2_000_000_000),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestProfileComputationMode:
    def test_known_members(self) -> None:
        assert ProfileComputationMode.EXACT.value == "exact"
        assert ProfileComputationMode.APPROXIMATE.value == "approximate"
        assert ProfileComputationMode.HYBRID.value == "hybrid"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProfileComputationMode("random")  # type: ignore[arg-type]


class TestProfileApproximationMethod:
    def test_known_members(self) -> None:
        assert ProfileApproximationMethod.RESERVOIR_SAMPLING.value == "reservoir_sampling"
        assert ProfileApproximationMethod.T_DIGEST.value == "t_digest"
        assert ProfileApproximationMethod.HLL.value == "hll"
        assert ProfileApproximationMethod.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProfileApproximationMethod("minhash")  # type: ignore[arg-type]


class TestOutlierDetectionMethod:
    def test_known_members(self) -> None:
        assert OutlierDetectionMethod.IQR.value == "iqr"
        assert OutlierDetectionMethod.ZSCORE.value == "zscore"
        assert OutlierDetectionMethod.NONE.value == "none"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            OutlierDetectionMethod("lof")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# QuantileSummary
# ---------------------------------------------------------------------------
class TestQuantileSummary:
    def test_minimal(self) -> None:
        q = QuantileSummary(quantile_pairs=((0.5, 1.0),))
        assert q.quantile_pairs == ((0.5, 1.0),)

    def test_empty_pairs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            QuantileSummary(quantile_pairs=())

    def test_quantile_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            QuantileSummary(quantile_pairs=((0.0, 1.0),))

    def test_quantile_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            QuantileSummary(quantile_pairs=((1.5, 1.0),))

    def test_quantile_one_ok(self) -> None:
        q = QuantileSummary(quantile_pairs=((1.0, 100.0),))
        assert q.quantile_pairs == ((1.0, 100.0),)

    def test_strictly_increasing_required(self) -> None:
        with pytest.raises(ValidationError):
            QuantileSummary(
                quantile_pairs=((0.5, 1.0), (0.5, 2.0))  # duplicate
            )

    def test_strictly_increasing_required_descending(self) -> None:
        with pytest.raises(ValidationError):
            QuantileSummary(
                quantile_pairs=((0.9, 1.0), (0.5, 2.0))  # descending
            )

    def test_round_trip(self) -> None:
        q = QuantileSummary(quantile_pairs=((0.25, 1.0), (0.5, 2.0), (0.75, 3.0)))
        assert QuantileSummary.model_validate(q.model_dump(mode="json")) == q


# ---------------------------------------------------------------------------
# FrequencySummary
# ---------------------------------------------------------------------------
class TestFrequencySummary:
    def test_empty(self) -> None:
        f = FrequencySummary()
        assert f.entries == ()
        assert f.truncated is False

    def test_with_entries(self) -> None:
        f = FrequencySummary(
            entries=(("a", 10), ("b", 5)),
            total_count=15,
            truncated=False,
            max_entries=10,
        )
        assert f.total_count == 15

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FrequencySummary(entries=(("a", -1),))

    def test_truncated_true_requires_enough_entries(self) -> None:
        with pytest.raises(ValidationError):
            FrequencySummary(
                entries=(("a", 1),),
                truncated=True,
                max_entries=10,
            )

    def test_truncated_false_with_many_entries_ok(self) -> None:
        f = FrequencySummary(
            entries=(("a", 1), ("b", 1)),
            truncated=False,
            max_entries=10,
        )
        assert f.truncated is False

    def test_round_trip(self) -> None:
        f = FrequencySummary(entries=(("a", 1),))
        assert FrequencySummary.model_validate(f.model_dump(mode="json")) == f


# ---------------------------------------------------------------------------
# DistributionSummary
# ---------------------------------------------------------------------------
class TestDistributionSummary:
    def test_minimal(self) -> None:
        d = DistributionSummary()
        assert d.min is None

    def test_full(self) -> None:
        d = DistributionSummary(
            min=0.0,
            max=10.0,
            mean=5.0,
            stddev=2.5,
            quantiles=QuantileSummary(quantile_pairs=((0.5, 5.0),)),
            is_bounded=True,
        )
        assert d.stddev == 2.5

    def test_negative_stddev_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DistributionSummary(stddev=-1.0)

    def test_max_lt_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DistributionSummary(min=10.0, max=5.0)

    def test_max_eq_min_ok(self) -> None:
        d = DistributionSummary(min=5.0, max=5.0)
        assert d.min == d.max

    def test_round_trip(self) -> None:
        d = DistributionSummary(min=0.0, max=1.0)
        assert DistributionSummary.model_validate(d.model_dump(mode="json")) == d


# ---------------------------------------------------------------------------
# NumericProfile
# ---------------------------------------------------------------------------
class TestNumericProfile:
    def test_minimal(self) -> None:
        n = NumericProfile(distribution=DistributionSummary(min=0.0, max=10.0))
        assert n.zero_count is None

    def test_with_sign_counts(self) -> None:
        n = NumericProfile(
            distribution=DistributionSummary(),
            zero_count=1,
            negative_count=2,
            positive_count=7,
            mean_abs=1.5,
            coefficient_of_variation=0.3,
        )
        assert n.zero_count == 1

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NumericProfile(distribution=DistributionSummary(), zero_count=-1)

    def test_round_trip(self) -> None:
        n = NumericProfile(distribution=DistributionSummary())
        assert NumericProfile.model_validate(n.model_dump(mode="json")) == n


# ---------------------------------------------------------------------------
# CategoricalProfile
# ---------------------------------------------------------------------------
class TestCategoricalProfile:
    def test_minimal(self) -> None:
        c = CategoricalProfile()
        assert c.distinct_count is None

    def test_full(self) -> None:
        c = CategoricalProfile(
            top_frequencies=FrequencySummary(entries=(("a", 5),)),
            distinct_count=2,
            most_frequent_value="a",
            most_frequent_count=5,
            least_frequent_count=1,
        )
        assert c.distinct_count == 2

    def test_most_frequent_pair_consistent(self) -> None:
        with pytest.raises(ValidationError):
            CategoricalProfile(
                most_frequent_value="a",
                # missing most_frequent_count
            )
        with pytest.raises(ValidationError):
            CategoricalProfile(
                most_frequent_count=5,
                # missing most_frequent_value
            )

    def test_round_trip(self) -> None:
        c = CategoricalProfile(distinct_count=5)
        assert CategoricalProfile.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# DatetimeProfile
# ---------------------------------------------------------------------------
class TestDatetimeProfile:
    def test_minimal(self) -> None:
        d = DatetimeProfile()
        assert d.min is None

    def test_full(self) -> None:
        d = DatetimeProfile(
            min=datetime(2026, 1, 1, tzinfo=timezone.utc),
            max=datetime(2026, 12, 31, tzinfo=timezone.utc),
            distinct_count=365,
        )
        assert d.distinct_count == 365

    def test_naive_min_max_normalized(self) -> None:
        d = DatetimeProfile(
            min=datetime(2026, 1, 1),
            max=datetime(2026, 12, 31),
        )
        assert d.min is not None
        assert d.min.tzinfo is timezone.utc
        assert d.max is not None
        assert d.max.tzinfo is timezone.utc

    def test_max_lt_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatetimeProfile(
                min=datetime(2026, 12, 31, tzinfo=timezone.utc),
                max=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_round_trip(self) -> None:
        d = DatetimeProfile(min=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert DatetimeProfile.model_validate(d.model_dump(mode="json")) == d


# ---------------------------------------------------------------------------
# MissingnessProfile / CardinalityProfile / DuplicateProfile
# ---------------------------------------------------------------------------
class TestMissingnessProfile:
    def test_minimal(self) -> None:
        m = MissingnessProfile()
        assert m.missing_count is None

    def test_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessProfile(missing_count=200, total_count=100)

    def test_ratio_bounds(self) -> None:
        MissingnessProfile(missing_ratio=0.0)
        MissingnessProfile(missing_ratio=1.0)

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessProfile(missing_ratio=1.5)


class TestCardinalityProfile:
    def test_minimal(self) -> None:
        c = CardinalityProfile()
        assert c.distinct_count is None

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CardinalityProfile(distinct_ratio=1.5)


class TestDuplicateProfile:
    def test_minimal(self) -> None:
        d = DuplicateProfile()
        assert d.duplicate_count is None

    def test_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DuplicateProfile(duplicate_count=200, total_count=100)

    def test_ratio_bounds(self) -> None:
        DuplicateProfile(duplicate_ratio=0.0)
        DuplicateProfile(duplicate_ratio=1.0)


# ---------------------------------------------------------------------------
# OutlierProfile
# ---------------------------------------------------------------------------
class TestOutlierProfile:
    def test_method_none_implies_no_counts(self) -> None:
        with pytest.raises(ValidationError):
            OutlierProfile(
                method=OutlierDetectionMethod.NONE,
                outlier_count=5,
            )

    def test_method_none_with_no_counts_ok(self) -> None:
        o = OutlierProfile(method=OutlierDetectionMethod.NONE)
        assert o.method is OutlierDetectionMethod.NONE
        assert o.outlier_count is None

    def test_iqr_with_bounds(self) -> None:
        o = OutlierProfile(
            method=OutlierDetectionMethod.IQR,
            outlier_count=2,
            total_count=100,
            outlier_ratio=0.02,
            lower_bound=0.0,
            upper_bound=100.0,
        )
        assert o.outlier_count == 2

    def test_bounds_inconsistent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OutlierProfile(
                method=OutlierDetectionMethod.IQR,
                outlier_count=1,
                total_count=100,
                lower_bound=10.0,
                upper_bound=5.0,
            )

    def test_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OutlierProfile(
                method=OutlierDetectionMethod.IQR,
                outlier_count=200,
                total_count=100,
            )

    def test_round_trip(self) -> None:
        o = OutlierProfile(
            method=OutlierDetectionMethod.IQR,
            outlier_count=1,
            total_count=10,
        )
        assert OutlierProfile.model_validate(o.model_dump(mode="json")) == o


# ---------------------------------------------------------------------------
# ColumnProfile
# ---------------------------------------------------------------------------
class TestColumnProfile:
    def test_minimal(self) -> None:
        c = ColumnProfile(column_name="amount")
        assert c.computation_mode is ProfileComputationMode.EXACT
        assert c.approximation_method is None
        assert c.sample_size is None

    def test_approximate_requires_method(self) -> None:
        with pytest.raises(ValidationError):
            ColumnProfile(
                column_name="amount",
                computation_mode=ProfileComputationMode.APPROXIMATE,
            )

    def test_approximate_with_method_ok(self) -> None:
        c = ColumnProfile(
            column_name="amount",
            computation_mode=ProfileComputationMode.APPROXIMATE,
            approximation_method=ProfileApproximationMethod.T_DIGEST,
            sample_size=10_000,
        )
        assert c.approximation_method is ProfileApproximationMethod.T_DIGEST

    def test_approximate_forbids_exact_method(self) -> None:
        with pytest.raises(ValidationError):
            ColumnProfile(
                column_name="amount",
                computation_mode=ProfileComputationMode.APPROXIMATE,
                approximation_method=ProfileApproximationMethod.EXACT,
            )

    def test_exact_forbids_sample_size(self) -> None:
        with pytest.raises(ValidationError):
            ColumnProfile(
                column_name="amount",
                computation_mode=ProfileComputationMode.EXACT,
                sample_size=10,
            )

    def test_with_per_type_profiles(self) -> None:
        c = ColumnProfile(
            column_name="amount",
            logical_type=LogicalDataType.FLOAT,
            numeric=NumericProfile(distribution=DistributionSummary()),
        )
        assert c.numeric is not None

    def test_round_trip(self) -> None:
        c = ColumnProfile(column_name="x")
        assert ColumnProfile.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# ConstantColumnWarning / HighCardinalityWarning
# ---------------------------------------------------------------------------
class TestConstantColumnWarning:
    def test_minimal(self) -> None:
        w = ConstantColumnWarning(column_name="x")
        assert w.severity is Severity.WARNING

    def test_full(self) -> None:
        w = ConstantColumnWarning(
            column_name="x",
            value="0",
            row_count=100,
            severity=Severity.WARNING,
            code="CONSTANT_COL",
            message="all values are 0",
        )
        assert w.row_count == 100

    def test_round_trip(self) -> None:
        w = ConstantColumnWarning(column_name="x", value="0")
        assert ConstantColumnWarning.model_validate(w.model_dump(mode="json")) == w


class TestHighCardinalityWarning:
    def test_minimal(self) -> None:
        w = HighCardinalityWarning(column_name="x")
        assert w.severity is Severity.WARNING

    def test_full(self) -> None:
        w = HighCardinalityWarning(
            column_name="x",
            distinct_count=1000,
            total_count=1000,
            distinct_ratio=1.0,
            threshold_ratio=0.5,
        )
        assert w.distinct_ratio == 1.0

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HighCardinalityWarning(column_name="x", distinct_ratio=1.5)

    def test_round_trip(self) -> None:
        w = HighCardinalityWarning(column_name="x", distinct_count=10)
        assert HighCardinalityWarning.model_validate(w.model_dump(mode="json")) == w


# ---------------------------------------------------------------------------
# ProfilingSpec
# ---------------------------------------------------------------------------
class TestProfilingSpec:
    def test_defaults(self) -> None:
        s = ProfilingSpec()
        assert s.compute_numeric is True
        assert s.compute_outliers is False

    def test_compute_outliers_requires_method(self) -> None:
        with pytest.raises(ValidationError):
            ProfilingSpec(compute_outliers=True)

    def test_compute_outliers_with_method_ok(self) -> None:
        s = ProfilingSpec(compute_outliers=True, outlier_method=OutlierDetectionMethod.IQR)
        assert s.outlier_method is OutlierDetectionMethod.IQR

    def test_compute_outliers_false_forbids_method(self) -> None:
        with pytest.raises(ValidationError):
            ProfilingSpec(
                compute_outliers=False,
                outlier_method=OutlierDetectionMethod.IQR,
            )


# ---------------------------------------------------------------------------
# ProfilingRequest
# ---------------------------------------------------------------------------
class TestProfilingRequest:
    def test_minimal(self) -> None:
        r = ProfilingRequest(
            dataset=_handle(),
            execution_limits=_default_execution_limits(),
        )
        assert r.spec.compute_numeric is True
        assert r.min_sample_size is None

    def test_sample_size_bounds(self) -> None:
        ProfilingRequest(
            dataset=_handle(),
            execution_limits=_default_execution_limits(),
            min_sample_size=100,
            max_sample_size=1000,
        )

    def test_max_lt_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProfilingRequest(
                dataset=_handle(),
                execution_limits=_default_execution_limits(),
                min_sample_size=1000,
                max_sample_size=100,
            )

    def test_full_request(self) -> None:
        r = ProfilingRequest(
            dataset=_handle(),
            spec=ProfilingSpec(compute_outliers=True, outlier_method=OutlierDetectionMethod.IQR),
            execution_limits=_default_execution_limits(),
            min_sample_size=100,
        )
        assert r.spec.compute_outliers is True


# ---------------------------------------------------------------------------
# DatasetProfile
# ---------------------------------------------------------------------------
class TestDatasetProfile:
    def test_minimal(self) -> None:
        p = DatasetProfile(dataset=_handle())
        assert p.column_profiles == ()
        assert p.computation_mode is ProfileComputationMode.EXACT

    def test_approximate_requires_method(self) -> None:
        with pytest.raises(ValidationError):
            DatasetProfile(
                dataset=_handle(),
                computation_mode=ProfileComputationMode.APPROXIMATE,
            )

    def test_approximate_with_method_ok(self) -> None:
        p = DatasetProfile(
            dataset=_handle(),
            computation_mode=ProfileComputationMode.APPROXIMATE,
            approximation_method=ProfileApproximationMethod.T_DIGEST,
        )
        assert p.approximation_method is ProfileApproximationMethod.T_DIGEST

    def test_approximate_forbids_exact_method(self) -> None:
        with pytest.raises(ValidationError):
            DatasetProfile(
                dataset=_handle(),
                computation_mode=ProfileComputationMode.APPROXIMATE,
                approximation_method=ProfileApproximationMethod.EXACT,
            )

    def test_with_column_profiles(self) -> None:
        p = DatasetProfile(
            dataset=_handle(),
            column_profiles=(
                ColumnProfile(column_name="id"),
                ColumnProfile(column_name="amount"),
            ),
        )
        assert len(p.column_profiles) == 2

    def test_duplicate_column_profile_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetProfile(
                dataset=_handle(),
                column_profiles=(
                    ColumnProfile(column_name="x"),
                    ColumnProfile(column_name="x"),
                ),
            )

    def test_duplicate_constant_column_warnings_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetProfile(
                dataset=_handle(),
                constant_column_warnings=(
                    ConstantColumnWarning(column_name="x"),
                    ConstantColumnWarning(column_name="x"),
                ),
            )

    def test_duplicate_high_cardinality_warnings_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetProfile(
                dataset=_handle(),
                high_cardinality_warnings=(
                    HighCardinalityWarning(column_name="x"),
                    HighCardinalityWarning(column_name="x"),
                ),
            )

    def test_naive_computed_at_normalized(self) -> None:
        p = DatasetProfile(
            dataset=_handle(),
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert p.computed_at is not None
        assert p.computed_at.tzinfo is timezone.utc

    def test_with_warnings_and_issues(self) -> None:
        p = DatasetProfile(
            dataset=_handle(),
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
        )
        assert len(p.issues) == 1

    def test_round_trip(self) -> None:
        p = DatasetProfile(
            dataset=_handle(),
            column_profiles=(ColumnProfile(column_name="id"),),
        )
        assert DatasetProfile.model_validate(p.model_dump(mode="json")) == p


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_profiling_contracts_do_not_import_heavy_libs() -> None:
    """Importing the profiling contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.profiling as profiling_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by profiling contracts: {leaked}"
