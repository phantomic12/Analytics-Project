"""Tests for diagnostic association contracts (Build Queue v2.1 Task 26).

Covers:

- ``CorrelationMethod`` valid/invalid values.
- ``AssociationCheckSpec`` defaults and bounded fields.
- ``AssociationCheckRequest`` invariants: target_column must not
  appear in feature_columns; feature column names are unique.
- ``PairwiseAssociationSummary`` invariants: pairs are canonically
  ordered (column_a < column_b); is_perfect is consistent with
  score; column_a and column_b differ.
- ``AssociationWarning`` validation and serialization.
- ``MulticollinearityRiskSummary`` invariants: high_risk_pair_count
  matches len(high_risk_pairs); pairs are canonically ordered; no
  self-pairs.
- ``AssociationCheckReport`` invariants: multicollinearity is
  consistent with the spec; pairwise pairs are unique;
  perfect_association_count matches the count of is_perfect=True
  summaries; computed_at coerced to UTC.

These tests intentionally avoid importing any heavy compute library
so that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.associations import (
    AssociationCheckReport,
    AssociationCheckRequest,
    AssociationCheckSpec,
    AssociationWarning,
    CorrelationMethod,
    MulticollinearityRiskSummary,
    PairwiseAssociationSummary,
)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _limits() -> ExecutionLimitPolicy:
    return ExecutionLimitPolicy(
        collect=CollectPolicy(mode=CollectMode.FORBIDDEN),
        pandas_conversion=PandasConversionPolicy(mode=PandasConversionMode.FORBIDDEN),
        memory_budget=MemoryBudgetPolicy(max_bytes=2_000_000_000),
    )


# ---------------------------------------------------------------------------
# CorrelationMethod
# ---------------------------------------------------------------------------
class TestCorrelationMethod:
    def test_known_members(self) -> None:
        assert CorrelationMethod.PEARSON.value == "pearson"
        assert CorrelationMethod.SPEARMAN.value == "spearman"
        assert CorrelationMethod.KENDALL.value == "kendall"
        assert CorrelationMethod.CRAMERS_V.value == "cramers_v"
        assert CorrelationMethod.PHI.value == "phi"
        assert CorrelationMethod.POINT_BISERIAL.value == "point_biserial"
        assert CorrelationMethod.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            CorrelationMethod("mutual_info")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AssociationCheckSpec
# ---------------------------------------------------------------------------
class TestAssociationCheckSpec:
    def test_defaults(self) -> None:
        s = AssociationCheckSpec()
        assert s.method is CorrelationMethod.PEARSON
        assert s.include_categorical is True
        assert s.max_pairs is None
        assert s.min_abs_score_to_report == 0.0
        assert s.emit_multicollinearity_summary is True

    def test_min_abs_score_bounds(self) -> None:
        AssociationCheckSpec(min_abs_score_to_report=0.0)
        AssociationCheckSpec(min_abs_score_to_report=1.0)

    def test_min_abs_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckSpec(min_abs_score_to_report=1.5)

    def test_negative_max_pairs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckSpec(max_pairs=-1)


# ---------------------------------------------------------------------------
# AssociationCheckRequest
# ---------------------------------------------------------------------------
class TestAssociationCheckRequest:
    def test_minimal(self) -> None:
        r = AssociationCheckRequest(dataset=_handle(), execution_limits=_limits())
        assert r.target_column is None
        assert r.feature_columns == ()

    def test_with_target_and_features(self) -> None:
        r = AssociationCheckRequest(
            dataset=_handle(),
            execution_limits=_limits(),
            target_column="amount",
            feature_columns=("age", "income"),
        )
        assert r.target_column == "amount"

    def test_target_in_features_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckRequest(
                dataset=_handle(),
                execution_limits=_limits(),
                target_column="amount",
                feature_columns=("amount", "age"),
            )

    def test_duplicate_feature_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckRequest(
                dataset=_handle(),
                execution_limits=_limits(),
                feature_columns=("x", "x"),
            )


# ---------------------------------------------------------------------------
# PairwiseAssociationSummary
# ---------------------------------------------------------------------------
class TestPairwiseAssociationSummary:
    def test_basic(self) -> None:
        p = PairwiseAssociationSummary(column_a="a", column_b="b", score=0.5)
        assert p.column_a == "a"
        assert p.column_b == "b"
        assert p.score == 0.5

    def test_canonical_ordering(self) -> None:
        # When the caller passes column_a > column_b, the validator
        # swaps so the pair is canonically ordered.
        p = PairwiseAssociationSummary(column_a="z", column_b="a", score=0.5)
        assert p.column_a == "a"
        assert p.column_b == "z"

    def test_self_pair_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PairwiseAssociationSummary(column_a="x", column_b="x", score=0.5)

    def test_score_bounds(self) -> None:
        PairwiseAssociationSummary(column_a="a", column_b="b", score=0.0)
        PairwiseAssociationSummary(column_a="a", column_b="b", score=1.0)

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PairwiseAssociationSummary(column_a="a", column_b="b", score=1.5)

    def test_is_perfect_consistent_with_score(self) -> None:
        # is_perfect=True requires score=1.0
        with pytest.raises(ValidationError):
            PairwiseAssociationSummary(column_a="a", column_b="b", score=0.9, is_perfect=True)
        # is_perfect=False forbids score=1.0
        with pytest.raises(ValidationError):
            PairwiseAssociationSummary(column_a="a", column_b="b", score=1.0, is_perfect=False)

    def test_is_perfect_default_none(self) -> None:
        p = PairwiseAssociationSummary(column_a="a", column_b="b", score=0.5)
        assert p.is_perfect is None

    def test_negative_sample_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PairwiseAssociationSummary(column_a="a", column_b="b", score=0.5, sample_size=-1)

    def test_round_trip(self) -> None:
        p = PairwiseAssociationSummary(column_a="a", column_b="b", score=0.7)
        assert PairwiseAssociationSummary.model_validate(p.model_dump(mode="json")) == p


# ---------------------------------------------------------------------------
# AssociationWarning
# ---------------------------------------------------------------------------
class TestAssociationWarning:
    def test_minimal(self) -> None:
        w = AssociationWarning(code="X", severity=Severity.WARNING, message="m")
        assert w.column_a is None

    def test_with_pair(self) -> None:
        w = AssociationWarning(
            code="X",
            severity=Severity.WARNING,
            message="m",
            column_a="a",
            column_b="b",
            score=0.95,
        )
        assert w.column_a == "a"
        assert w.score == 0.95

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationWarning(code="X", severity=Severity.WARNING, message="m", score=1.5)

    def test_round_trip(self) -> None:
        w = AssociationWarning(code="X", severity=Severity.WARNING, message="m")
        assert AssociationWarning.model_validate(w.model_dump(mode="json")) == w


# ---------------------------------------------------------------------------
# MulticollinearityRiskSummary
# ---------------------------------------------------------------------------
class TestMulticollinearityRiskSummary:
    def test_minimal(self) -> None:
        m = MulticollinearityRiskSummary(high_risk_threshold=0.8)
        assert m.high_risk_pair_count is None
        assert m.high_risk_pairs == ()

    def test_with_pairs(self) -> None:
        m = MulticollinearityRiskSummary(
            high_risk_threshold=0.8,
            high_risk_pair_count=2,
            high_risk_pairs=(("a", "b"), ("c", "d")),
        )
        assert m.high_risk_pair_count == 2

    def test_pair_count_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MulticollinearityRiskSummary(
                high_risk_threshold=0.8,
                high_risk_pair_count=1,
                high_risk_pairs=(("a", "b"), ("c", "d")),
            )

    def test_self_pair_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MulticollinearityRiskSummary(
                high_risk_threshold=0.8,
                high_risk_pair_count=1,
                high_risk_pairs=(("a", "a"),),
            )

    def test_canonical_ordering_required(self) -> None:
        with pytest.raises(ValidationError):
            MulticollinearityRiskSummary(
                high_risk_threshold=0.8,
                high_risk_pair_count=1,
                high_risk_pairs=(("z", "a"),),
            )

    def test_threshold_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MulticollinearityRiskSummary(high_risk_threshold=1.5)

    def test_negative_max_vif_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MulticollinearityRiskSummary(high_risk_threshold=0.8, max_vif=-0.1)

    def test_round_trip(self) -> None:
        m = MulticollinearityRiskSummary(
            high_risk_threshold=0.8,
            high_risk_pair_count=1,
            high_risk_pairs=(("a", "b"),),
        )
        assert MulticollinearityRiskSummary.model_validate(m.model_dump(mode="json")) == m


# ---------------------------------------------------------------------------
# AssociationCheckReport
# ---------------------------------------------------------------------------
class TestAssociationCheckReport:
    def test_minimal(self) -> None:
        r = AssociationCheckReport(dataset=_handle(), spec=AssociationCheckSpec())
        assert r.pairwise_summaries == ()
        assert r.multicollinearity is None

    def test_with_summaries(self) -> None:
        r = AssociationCheckReport(
            dataset=_handle(),
            spec=AssociationCheckSpec(),
            pairwise_summaries=(
                PairwiseAssociationSummary(column_a="a", column_b="b", score=0.7),
                PairwiseAssociationSummary(column_a="a", column_b="c", score=0.5),
            ),
        )
        assert len(r.pairwise_summaries) == 2

    def test_duplicate_pairs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckReport(
                dataset=_handle(),
                spec=AssociationCheckSpec(),
                pairwise_summaries=(
                    PairwiseAssociationSummary(column_a="a", column_b="b", score=0.5),
                    PairwiseAssociationSummary(column_a="a", column_b="b", score=0.7),
                ),
            )

    def test_multicollinearity_inconsistent_with_spec_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssociationCheckReport(
                dataset=_handle(),
                spec=AssociationCheckSpec(emit_multicollinearity_summary=False),
                multicollinearity=MulticollinearityRiskSummary(high_risk_threshold=0.8),
            )

    def test_perfect_association_count_consistent(self) -> None:
        with pytest.raises(ValidationError):
            # Claim 1 perfect but the summaries are not is_perfect.
            AssociationCheckReport(
                dataset=_handle(),
                spec=AssociationCheckSpec(),
                pairwise_summaries=(
                    PairwiseAssociationSummary(column_a="a", column_b="b", score=0.7),
                ),
                perfect_association_count=1,
            )

    def test_perfect_association_count_match(self) -> None:
        r = AssociationCheckReport(
            dataset=_handle(),
            spec=AssociationCheckSpec(),
            pairwise_summaries=(
                PairwiseAssociationSummary(column_a="a", column_b="b", score=1.0, is_perfect=True),
            ),
            perfect_association_count=1,
        )
        assert r.perfect_association_count == 1

    def test_with_issues_and_warnings(self) -> None:
        r = AssociationCheckReport(
            dataset=_handle(),
            spec=AssociationCheckSpec(),
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            common_warnings=(WarningRecord(code="W", message="m"),),
            warnings=(AssociationWarning(code="X", severity=Severity.WARNING, message="m"),),
        )
        assert len(r.issues) == 1

    def test_naive_computed_at_normalized(self) -> None:
        r = AssociationCheckReport(
            dataset=_handle(),
            spec=AssociationCheckSpec(),
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.computed_at is not None
        assert r.computed_at.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        r = AssociationCheckReport(dataset=_handle(), spec=AssociationCheckSpec())
        assert AssociationCheckReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_associations_contracts_do_not_import_heavy_libs() -> None:
    """Importing the associations contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.associations as associations_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by associations contracts: {leaked}"
