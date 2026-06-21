"""Tests for data quality and missingness contracts (Build Queue v2.1 Task 24).

Covers:

- ``ColumnMissingness`` / ``RowMissingnessSummary`` /
  ``MissingnessPatternSummary`` validation, invariants, and
  serialization round-trips.
- ``JoinIntroducedMissingness`` and ``ModelExclusionSummary`` /
  ``ModelExclusionReason`` validation.
- ``DataQualityIssue`` / ``DataQualityIssueKind`` validation.
- ``MissingDataReport`` invariants (unique column names, computed_at
  timezone coercion).
- ``DataQualityReport`` invariants (``is_passthrough_clean=True``
  forbids ERROR/CRITICAL issues; unique model-exclusion column names;
  computed_at timezone coercion).

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
from analytics_platform.contracts.quality import (
    ColumnMissingness,
    DataQualityIssue,
    DataQualityIssueKind,
    DataQualityReport,
    JoinIntroducedMissingness,
    MissingDataReport,
    MissingnessPatternSummary,
    ModelExclusionReason,
    ModelExclusionSummary,
    RowMissingnessSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle(name: str = "orders") -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name=name)


def _column_missingness(
    column_name: str = "amount",
    missing_count: int | None = 5,
    total_count: int | None = 100,
    missing_ratio: float | None = 0.05,
) -> ColumnMissingness:
    return ColumnMissingness(
        column_name=column_name,
        missing_count=missing_count,
        total_count=total_count,
        missing_ratio=missing_ratio,
    )


# ---------------------------------------------------------------------------
# ColumnMissingness
# ---------------------------------------------------------------------------
class TestColumnMissingness:
    def test_minimal(self) -> None:
        c = ColumnMissingness(column_name="amount")
        assert c.missing_count is None
        assert c.total_count is None
        assert c.missing_ratio is None
        assert c.is_constant is None
        assert c.conditionally_missing_on == ()

    def test_full(self) -> None:
        c = _column_missingness()
        assert c.missing_count == 5
        assert c.total_count == 100
        assert c.missing_ratio == 0.05

    def test_missing_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="amount", missing_count=200, total_count=100)

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="amount", missing_count=-1)
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="amount", total_count=-1)

    def test_missing_ratio_bounds(self) -> None:
        ColumnMissingness(column_name="amount", missing_ratio=0.0)
        ColumnMissingness(column_name="amount", missing_ratio=1.0)

    def test_missing_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="amount", missing_ratio=1.5)

    def test_missing_ratio_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="amount", missing_ratio=-0.1)

    def test_empty_column_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnMissingness(column_name="")

    def test_round_trip(self) -> None:
        c = _column_missingness()
        assert ColumnMissingness.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# RowMissingnessSummary
# ---------------------------------------------------------------------------
class TestRowMissingnessSummary:
    def test_minimal(self) -> None:
        s = RowMissingnessSummary()
        assert s.total_rows is None
        assert s.missing_per_row_histogram == ()

    def test_full(self) -> None:
        s = RowMissingnessSummary(
            total_rows=100,
            complete_rows=80,
            min_missing_per_row=0,
            max_missing_per_row=3,
            mean_missing_per_row=0.4,
            missing_per_row_histogram=((0, 80), (1, 10), (2, 5), (3, 5)),
        )
        assert s.total_rows == 100
        assert s.complete_rows == 80

    def test_complete_rows_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(total_rows=10, complete_rows=20)

    def test_min_max_inconsistent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(min_missing_per_row=3, max_missing_per_row=1)

    def test_min_max_equal_ok(self) -> None:
        s = RowMissingnessSummary(min_missing_per_row=2, max_missing_per_row=2)
        assert s.min_missing_per_row == s.max_missing_per_row

    def test_negative_mean_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(mean_missing_per_row=-0.1)

    def test_histogram_keys_must_be_increasing(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(missing_per_row_histogram=((3, 1), (2, 1)))

    def test_histogram_keys_must_be_unique(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(missing_per_row_histogram=((1, 5), (1, 6)))

    def test_histogram_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowMissingnessSummary(missing_per_row_histogram=((1, -1),))

    def test_round_trip(self) -> None:
        s = RowMissingnessSummary(total_rows=10)
        assert RowMissingnessSummary.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# MissingnessPatternSummary
# ---------------------------------------------------------------------------
class TestMissingnessPatternSummary:
    def test_empty(self) -> None:
        s = MissingnessPatternSummary()
        assert s.patterns == ()

    def test_with_patterns(self) -> None:
        s = MissingnessPatternSummary(
            patterns=(("only_a", 5), ("a_and_b", 2)),
            max_patterns=10,
        )
        assert len(s.patterns) == 2

    def test_duplicate_pattern_labels_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessPatternSummary(patterns=(("a", 1), ("a", 2)))

    def test_empty_pattern_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessPatternSummary(patterns=(("", 1),))

    def test_long_pattern_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessPatternSummary(patterns=(("x" * 257, 1),))

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessPatternSummary(patterns=(("a", -1),))

    def test_patterns_exceed_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingnessPatternSummary(patterns=(("a", 1), ("b", 1)), max_patterns=1)

    def test_round_trip(self) -> None:
        s = MissingnessPatternSummary(patterns=(("a", 1),))
        assert MissingnessPatternSummary.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# JoinIntroducedMissingness
# ---------------------------------------------------------------------------
class TestJoinIntroducedMissingness:
    def test_minimal(self) -> None:
        j = JoinIntroducedMissingness(column_name="right_col")
        assert j.introduced_missing_count is None

    def test_with_introduced(self) -> None:
        j = JoinIntroducedMissingness(
            column_name="right_col",
            introduced_missing_count=10,
            total_count=100,
            introduced_missing_ratio=0.1,
            source_role="right",
        )
        assert j.introduced_missing_ratio == 0.1

    def test_introduced_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinIntroducedMissingness(
                column_name="right_col",
                introduced_missing_count=200,
                total_count=100,
            )

    def test_round_trip(self) -> None:
        j = JoinIntroducedMissingness(column_name="c", introduced_missing_count=5)
        assert JoinIntroducedMissingness.model_validate(j.model_dump(mode="json")) == j


# ---------------------------------------------------------------------------
# ModelExclusionSummary
# ---------------------------------------------------------------------------
class TestModelExclusionSummary:
    def test_minimal(self) -> None:
        e = ModelExclusionSummary(column_name="id", reason=ModelExclusionReason.IDENTIFIER)
        assert e.detail is None
        assert e.missing_ratio is None

    def test_full(self) -> None:
        e = ModelExclusionSummary(
            column_name="amount",
            reason=ModelExclusionReason.HIGH_MISSINGNESS,
            detail="too many missing values",
            missing_ratio=0.8,
            run_id="r1",
        )
        assert e.missing_ratio == 0.8

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelExclusionSummary(
                column_name="x",
                reason=ModelExclusionReason.HIGH_MISSINGNESS,
                missing_ratio=1.5,
            )

    def test_round_trip(self) -> None:
        e = ModelExclusionSummary(column_name="x", reason=ModelExclusionReason.IDENTIFIER)
        assert ModelExclusionSummary.model_validate(e.model_dump(mode="json")) == e


# ---------------------------------------------------------------------------
# DataQualityIssue
# ---------------------------------------------------------------------------
class TestDataQualityIssue:
    def test_minimal(self) -> None:
        i = DataQualityIssue(
            code="COL_HIGH_MISSINGNESS",
            kind=DataQualityIssueKind.HIGH_MISSINGNESS,
            severity=Severity.WARNING,
            message="too many missing",
        )
        assert i.column_name is None

    def test_full(self) -> None:
        i = DataQualityIssue(
            code="COL_HIGH_MISSINGNESS",
            kind=DataQualityIssueKind.HIGH_MISSINGNESS,
            severity=Severity.ERROR,
            message="too many missing",
            column_name="amount",
            observed_value="missing_ratio=0.42",
            threshold="0.1",
            row_count_affected=42,
        )
        assert i.column_name == "amount"
        assert i.row_count_affected == 42

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataQualityIssue(
                code="",
                kind=DataQualityIssueKind.OTHER,
                severity=Severity.WARNING,
                message="m",
            )

    def test_negative_row_count_affected_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataQualityIssue(
                code="X",
                kind=DataQualityIssueKind.OTHER,
                severity=Severity.WARNING,
                message="m",
                row_count_affected=-1,
            )

    def test_round_trip(self) -> None:
        i = DataQualityIssue(
            code="X",
            kind=DataQualityIssueKind.OTHER,
            severity=Severity.WARNING,
            message="m",
        )
        assert DataQualityIssue.model_validate(i.model_dump(mode="json")) == i


# ---------------------------------------------------------------------------
# MissingDataReport
# ---------------------------------------------------------------------------
def _missing_data_report() -> MissingDataReport:
    return MissingDataReport(
        dataset=_handle(),
        column_missingness=(
            ColumnMissingness(column_name="amount", missing_count=5, total_count=100),
            ColumnMissingness(column_name="name", missing_count=1, total_count=100),
        ),
        row_summary=RowMissingnessSummary(total_rows=100, complete_rows=94),
        pattern_summary=MissingnessPatternSummary(patterns=(("only_amount", 5),)),
    )


class TestMissingDataReport:
    def test_minimal(self) -> None:
        r = MissingDataReport(dataset=_handle())
        assert r.column_missingness == ()

    def test_full(self) -> None:
        r = _missing_data_report()
        assert len(r.column_missingness) == 2
        assert r.row_summary is not None
        assert r.pattern_summary is not None

    def test_duplicate_column_missingness_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingDataReport(
                dataset=_handle(),
                column_missingness=(
                    _column_missingness("amount"),
                    _column_missingness("amount"),
                ),
            )

    def test_duplicate_join_introduced_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingDataReport(
                dataset=_handle(),
                join_introduced_missingness=(
                    JoinIntroducedMissingness(column_name="a"),
                    JoinIntroducedMissingness(column_name="a"),
                ),
            )

    def test_naive_computed_at_normalized(self) -> None:
        r = MissingDataReport(
            dataset=_handle(),
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.computed_at is not None
        assert r.computed_at.tzinfo is timezone.utc

    def test_aware_computed_at_preserved(self) -> None:
        aware = datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc)
        r = MissingDataReport(dataset=_handle(), computed_at=aware)
        assert r.computed_at == aware

    def test_round_trip(self) -> None:
        r = _missing_data_report()
        assert MissingDataReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# DataQualityReport
# ---------------------------------------------------------------------------
class TestDataQualityReport:
    def test_minimal(self) -> None:
        r = DataQualityReport(dataset=_handle(), missing_data=MissingDataReport(dataset=_handle()))
        assert r.quality_issues == ()
        assert r.model_exclusions == ()

    def test_full(self) -> None:
        r = DataQualityReport(
            dataset=_handle(),
            missing_data=_missing_data_report(),
            quality_issues=(
                DataQualityIssue(
                    code="COL_HIGH_MISSINGNESS",
                    kind=DataQualityIssueKind.HIGH_MISSINGNESS,
                    severity=Severity.WARNING,
                    message="m",
                ),
            ),
            model_exclusions=(
                ModelExclusionSummary(
                    column_name="id",
                    reason=ModelExclusionReason.IDENTIFIER,
                ),
            ),
            has_target_associated_missingness=False,
            is_passthrough_clean=True,
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
        )
        assert r.is_passthrough_clean is True

    def test_duplicate_model_exclusion_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataQualityReport(
                dataset=_handle(),
                missing_data=MissingDataReport(dataset=_handle()),
                model_exclusions=(
                    ModelExclusionSummary(
                        column_name="x",
                        reason=ModelExclusionReason.IDENTIFIER,
                    ),
                    ModelExclusionSummary(
                        column_name="x",
                        reason=ModelExclusionReason.CONSTANT_COLUMN,
                    ),
                ),
            )

    def test_passthrough_clean_forbids_error_quality_issue(self) -> None:
        with pytest.raises(ValidationError):
            DataQualityReport(
                dataset=_handle(),
                missing_data=MissingDataReport(dataset=_handle()),
                quality_issues=(
                    DataQualityIssue(
                        code="ERR",
                        kind=DataQualityIssueKind.OTHER,
                        severity=Severity.ERROR,
                        message="e",
                    ),
                ),
                is_passthrough_clean=True,
            )

    def test_passthrough_clean_forbids_error_common_issue(self) -> None:
        with pytest.raises(ValidationError):
            DataQualityReport(
                dataset=_handle(),
                missing_data=MissingDataReport(dataset=_handle()),
                issues=(Issue(code="ERR", severity=Severity.ERROR, message="e"),),
                is_passthrough_clean=True,
            )

    def test_passthrough_clean_with_warnings_ok(self) -> None:
        r = DataQualityReport(
            dataset=_handle(),
            missing_data=MissingDataReport(dataset=_handle()),
            quality_issues=(
                DataQualityIssue(
                    code="WARN",
                    kind=DataQualityIssueKind.OTHER,
                    severity=Severity.WARNING,
                    message="w",
                ),
            ),
            is_passthrough_clean=True,
        )
        assert r.is_passthrough_clean is True

    def test_round_trip(self) -> None:
        r = DataQualityReport(dataset=_handle(), missing_data=_missing_data_report())
        assert DataQualityReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_quality_contracts_do_not_import_heavy_libs() -> None:
    """Importing the quality contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.quality as quality_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by quality contracts: {leaked}"
