"""Tests for statistics contracts (Build Queue v2.1 Task 32)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.statistics import (
    ConfidenceInterval,
    EffectEstimate,
    MultipleTestingCorrectionMethod,
    MultipleTestingCorrectionReport,
    PValueAdjustmentResult,
    StatisticalTestResult,
    TestFamily,
)


class TestEnums:
    def test_correction_methods(self) -> None:
        assert MultipleTestingCorrectionMethod.BONFERRONI.value == "bonferroni"
        assert MultipleTestingCorrectionMethod.HOLM.value == "holm"
        assert (
            MultipleTestingCorrectionMethod.BENJAMINI_HOCHBERG.value
            == "benjamini_hochberg"
        )

    def test_test_families(self) -> None:
        assert TestFamily.COEFFICIENT.value == "coefficient"
        assert TestFamily.ASSOCIATION.value == "association"
        assert TestFamily.GROUP_DIFFERENCE.value == "group_difference"

    def test_invalid_values_rejected(self) -> None:
        with pytest.raises(ValueError):
            MultipleTestingCorrectionMethod("fdr")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            TestFamily("regression")  # type: ignore[arg-type]


class TestConfidenceInterval:
    def test_basic(self) -> None:
        ci = ConfidenceInterval(lower=0.0, upper=1.0, confidence_level=0.95)
        assert ci.lower == 0.0

    def test_upper_lt_lower_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConfidenceInterval(lower=1.0, upper=0.5)

    def test_confidence_level_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ConfidenceInterval(lower=0.0, upper=1.0, confidence_level=1.5)

    def test_round_trip(self) -> None:
        ci = ConfidenceInterval(lower=0.0, upper=1.0)
        assert ConfidenceInterval.model_validate(ci.model_dump(mode="json")) == ci


class TestEffectEstimate:
    def test_basic(self) -> None:
        e = EffectEstimate(point=1.5)
        assert e.standard_error is None

    def test_negative_standard_error_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EffectEstimate(point=1.0, standard_error=-0.1)


class TestPValueAdjustmentResult:
    def test_basic(self) -> None:
        p = PValueAdjustmentResult(
            hypothesis_id="h1", raw_p_value=0.01, adjusted_p_value=0.04
        )
        assert p.rank is None

    def test_rank_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            PValueAdjustmentResult(
                hypothesis_id="h1",
                raw_p_value=0.01,
                adjusted_p_value=0.04,
                rank=0,
            )

    def test_p_value_bounds(self) -> None:
        with pytest.raises(ValidationError):
            PValueAdjustmentResult(
                hypothesis_id="h1", raw_p_value=-0.1, adjusted_p_value=0.04
            )
        with pytest.raises(ValidationError):
            PValueAdjustmentResult(
                hypothesis_id="h1", raw_p_value=0.01, adjusted_p_value=1.5
            )


class TestStatisticalTestResult:
    def test_basic(self) -> None:
        r = StatisticalTestResult(
            test_id="t1",
            family=TestFamily.COEFFICIENT,
            statistic=2.5,
            p_value=0.01,
        )
        assert r.degrees_of_freedom is None

    def test_negative_dof_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StatisticalTestResult(
                test_id="t1",
                family=TestFamily.COEFFICIENT,
                statistic=2.5,
                p_value=0.01,
                degrees_of_freedom=-1.0,
            )


class TestMultipleTestingCorrectionReport:
    def test_basic(self) -> None:
        r = MultipleTestingCorrectionReport(
            family=TestFamily.COEFFICIENT,
            correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
            alpha=0.05,
        )
        assert r.skipped is False

    def test_with_adjustments(self) -> None:
        r = MultipleTestingCorrectionReport(
            family=TestFamily.COEFFICIENT,
            correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
            alpha=0.05,
            adjustments=(
                PValueAdjustmentResult(
                    hypothesis_id="h1",
                    raw_p_value=0.01,
                    adjusted_p_value=0.04,
                ),
            ),
        )
        assert len(r.adjustments) == 1

    def test_skipped_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.NONE,
                alpha=0.05,
                skipped=True,
            )

    def test_skipped_with_reason_ok(self) -> None:
        r = MultipleTestingCorrectionReport(
            family=TestFamily.COEFFICIENT,
            correction_method=MultipleTestingCorrectionMethod.NONE,
            alpha=0.05,
            skipped=True,
            skip_reason="family has only one test",
        )
        assert r.skipped is True

    def test_not_skipped_forbids_reason(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
                alpha=0.05,
                skip_reason="not actually skipped",
            )

    def test_correction_method_none_requires_skipped(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.NONE,
                alpha=0.05,
                skipped=False,
            )

    def test_n_rejected_exceeds_n_tests_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
                alpha=0.05,
                n_tests=5,
                n_rejected=10,
            )

    def test_duplicate_hypothesis_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
                alpha=0.05,
                adjustments=(
                    PValueAdjustmentResult(
                        hypothesis_id="h1",
                        raw_p_value=0.01,
                        adjusted_p_value=0.04,
                    ),
                    PValueAdjustmentResult(
                        hypothesis_id="h1",
                        raw_p_value=0.02,
                        adjusted_p_value=0.08,
                    ),
                ),
            )

    def test_alpha_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
                alpha=1.5,
            )

    def test_with_issues_and_warnings(self) -> None:
        r = MultipleTestingCorrectionReport(
            family=TestFamily.COEFFICIENT,
            correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
            alpha=0.05,
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
        )
        assert len(r.issues) == 1

    def test_round_trip(self) -> None:
        r = MultipleTestingCorrectionReport(
            family=TestFamily.COEFFICIENT,
            correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
            alpha=0.05,
        )
        assert MultipleTestingCorrectionReport.model_validate(
            r.model_dump(mode="json")
        ) == r


def test_statistics_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.statistics as statistics_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by statistics contracts: {leaked}"
