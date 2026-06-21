"""Tests for validation contracts (Build Queue v2.1 Tasks 36-38)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    ModelId,
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
from analytics_platform.contracts.features import (
    FeatureBuildRequest,
    FeatureSpec,
    SplitSpec,
    TargetSpec,
    TargetTask,
)
from analytics_platform.contracts.modeling import (
    CoefficientTable,
    ModelAssumptionDiagnostics,
    ModelDataDiagnostics,
    ModelDiagnosticReport,
    ModelResult,
    ModelStabilityDiagnostics,
)
from analytics_platform.contracts.statistics import (
    MultipleTestingCorrectionMethod,
    MultipleTestingCorrectionReport,
    TestFamily,
)
from analytics_platform.contracts.validation import (
    ApprovedWording,
    CausalClaimPolicy,
    CausalWarning,
    ClaimLevel,
    DisallowedWording,
    EvidenceGrade,
    ModelValidationReport,
    ModelValidationRequest,
    RejectedModelInterpretation,
    RobustnessCheckResult,
    RobustnessCheckSpec,
    SkippedRobustnessCheck,
    ValidatedModelInterpretation,
    ValidationSpec,
    ValidationStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _limits() -> ExecutionLimitPolicy:
    return ExecutionLimitPolicy(
        collect=CollectPolicy(mode=CollectMode.FORBIDDEN),
        pandas_conversion=PandasConversionPolicy(
            mode=PandasConversionMode.FORBIDDEN
        ),
        memory_budget=MemoryBudgetPolicy(max_bytes=2_000_000_000),
    )


def _feature_build() -> FeatureBuildRequest:
    return FeatureBuildRequest(
        dataset=_handle(),
        target=TargetSpec(column_name="amount", task=TargetTask.REGRESSION),
        features=(FeatureSpec(column_name="age"),),
        split=SplitSpec(),
    )


def _model_result() -> ModelResult:
    return ModelResult(
        model_id="m1",
        coefficient_table=CoefficientTable(
            coefficients=(),
        ),
    )


def _diagnostics() -> ModelDiagnosticReport:
    return ModelDiagnosticReport(
        model_id="m1",
        assumptions=ModelAssumptionDiagnostics(),
        data_diagnostics=ModelDataDiagnostics(),
        stability=ModelStabilityDiagnostics(),
    )


def _validation_request() -> ModelValidationRequest:
    return ModelValidationRequest(
        model_id="m1",
        result=_model_result(),
        diagnostics=_diagnostics(),
        spec=ValidationSpec(),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestEnums:
    def test_claim_level_known_members(self) -> None:
        assert ClaimLevel.CAUSAL.value == "causal"
        assert ClaimLevel.QUASI_CAUSAL.value == "quasi_causal"
        assert ClaimLevel.EXPLANATORY.value == "explanatory"
        assert ClaimLevel.DESCRIPTIVE.value == "descriptive"
        assert ClaimLevel.EXPLORATORY.value == "exploratory"

    def test_evidence_grade_known_members(self) -> None:
        assert EvidenceGrade.STRONG.value == "strong"
        assert EvidenceGrade.MODERATE.value == "moderate"
        assert EvidenceGrade.WEAK.value == "weak"
        assert EvidenceGrade.INSUFFICIENT.value == "insufficient"

    def test_causal_claim_policy_known_members(self) -> None:
        assert CausalClaimPolicy.BLOCK.value == "block"
        assert CausalClaimPolicy.DOWNGRADE.value == "downgrade"
        assert CausalClaimPolicy.ALLOW.value == "allow"

    def test_validation_strategy_known_members(self) -> None:
        assert ValidationStrategy.STANDARD.value == "standard"
        assert ValidationStrategy.CONSERVATIVE.value == "conservative"
        assert ValidationStrategy.EXPLORATORY.value == "exploratory"


# ---------------------------------------------------------------------------
# CausalWarning
# ---------------------------------------------------------------------------
class TestCausalWarning:
    def test_basic(self) -> None:
        w = CausalWarning(
            code="X",
            severity=Severity.WARNING,
            message="m",
            attempted_claim_level=ClaimLevel.CAUSAL,
            downgraded_to=ClaimLevel.EXPLANATORY,
        )
        assert w.related_claim_text is None

    def test_invalid_downgrade_rejected(self) -> None:
        # Can't downgrade CAUSAL to DESCRIPTIVE? Actually DESCRIPTIVE
        # is weaker than EXPLANATORY, so it's allowed. Try the
        # opposite: attempted DESCRIPTIVE, downgraded to CAUSAL.
        with pytest.raises(ValidationError):
            CausalWarning(
                code="X",
                severity=Severity.WARNING,
                message="m",
                attempted_claim_level=ClaimLevel.DESCRIPTIVE,
                downgraded_to=ClaimLevel.CAUSAL,
            )

    def test_non_causal_attempted_rejected(self) -> None:
        # Only CAUSAL / QUASI_CAUSAL can be the attempted_claim_level
        with pytest.raises(ValidationError):
            CausalWarning(
                code="X",
                severity=Severity.WARNING,
                message="m",
                attempted_claim_level=ClaimLevel.EXPLANATORY,
                downgraded_to=ClaimLevel.DESCRIPTIVE,
            )

    def test_round_trip(self) -> None:
        w = CausalWarning(
            code="X",
            severity=Severity.WARNING,
            message="m",
            attempted_claim_level=ClaimLevel.CAUSAL,
            downgraded_to=ClaimLevel.EXPLANATORY,
        )
        assert CausalWarning.model_validate(w.model_dump(mode="json")) == w


# ---------------------------------------------------------------------------
# ApprovedWording / DisallowedWording
# ---------------------------------------------------------------------------
class TestWordingRecords:
    def test_approved(self) -> None:
        a = ApprovedWording(
            claim_level=ClaimLevel.EXPLANATORY,
            min_evidence_grade=EvidenceGrade.MODERATE,
            text="associated with",
        )
        assert a.context is None

    def test_disallowed(self) -> None:
        d = DisallowedWording(
            claim_level=ClaimLevel.EXPLANATORY,
            pattern="causes",
            reason="causal claim at this level is blocked",
        )
        assert d.context is None

    def test_empty_approved_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ApprovedWording(
                claim_level=ClaimLevel.EXPLANATORY,
                min_evidence_grade=EvidenceGrade.MODERATE,
                text="",
            )


# ---------------------------------------------------------------------------
# RobustnessCheckSpec / RobustnessCheckResult / SkippedRobustnessCheck
# ---------------------------------------------------------------------------
class TestRobustnessChecks:
    def test_spec(self) -> None:
        s = RobustnessCheckSpec()
        assert s.require_holdout is True

    def test_perturbation_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RobustnessCheckSpec(min_sample_perturbation_fraction=1.5)

    def test_negative_max_severe_violations_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RobustnessCheckSpec(max_severe_violations=-1)

    def test_result(self) -> None:
        r = RobustnessCheckResult(
            check_name="stability",
            passed=True,
            severity=Severity.INFO,
            message="ok",
        )
        assert r.observed_metric is None

    def test_skipped(self) -> None:
        s = SkippedRobustnessCheck(
            check_name="stability",
            reason="holdout not configured",
        )
        assert s.severity is Severity.WARNING


# ---------------------------------------------------------------------------
# ValidationSpec
# ---------------------------------------------------------------------------
class TestValidationSpec:
    def test_defaults(self) -> None:
        s = ValidationSpec()
        assert s.strategy is ValidationStrategy.STANDARD
        assert s.causal_claim_policy is CausalClaimPolicy.BLOCK
        assert s.max_allowed_claim_level is ClaimLevel.EXPLANATORY
        assert s.min_evidence_grade is EvidenceGrade.MODERATE
        assert s.fail_on_rejection is True

    def test_causal_claim_policy_allow_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationSpec(causal_claim_policy=CausalClaimPolicy.ALLOW)

    def test_max_allowed_claim_level_causal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationSpec(max_allowed_claim_level=ClaimLevel.CAUSAL)

    def test_max_allowed_claim_level_quasi_causal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ValidationSpec(
                max_allowed_claim_level=ClaimLevel.QUASI_CAUSAL
            )

    def test_downgrade_allowed(self) -> None:
        s = ValidationSpec(causal_claim_policy=CausalClaimPolicy.DOWNGRADE)
        assert s.causal_claim_policy is CausalClaimPolicy.DOWNGRADE


# ---------------------------------------------------------------------------
# ModelValidationRequest
# ---------------------------------------------------------------------------
class TestModelValidationRequest:
    def test_basic(self) -> None:
        r = _validation_request()
        assert r.spec.causal_claim_policy is CausalClaimPolicy.BLOCK

    def test_result_model_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationRequest(
                model_id="m1",
                result=ModelResult(
                    model_id="m2",
                    coefficient_table=CoefficientTable(),
                ),
                diagnostics=_diagnostics(),
            )

    def test_diagnostics_model_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationRequest(
                model_id="m1",
                result=_model_result(),
                diagnostics=ModelDiagnosticReport(
                    model_id="m2",
                    assumptions=ModelAssumptionDiagnostics(),
                    data_diagnostics=ModelDataDiagnostics(),
                    stability=ModelStabilityDiagnostics(),
                ),
            )

    def test_with_robustness_checks(self) -> None:
        r = ModelValidationRequest(
            model_id="m1",
            result=_model_result(),
            diagnostics=_diagnostics(),
            robustness_checks=(
                RobustnessCheckResult(
                    check_name="stability",
                    passed=True,
                    severity=Severity.INFO,
                    message="ok",
                ),
            ),
            skipped_robustness_checks=(
                SkippedRobustnessCheck(
                    check_name="other", reason="not configured"
                ),
            ),
        )
        assert len(r.robustness_checks) == 1

    def test_duplicate_robustness_check_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationRequest(
                model_id="m1",
                result=_model_result(),
                diagnostics=_diagnostics(),
                robustness_checks=(
                    RobustnessCheckResult(
                        check_name="stability",
                        passed=True,
                        severity=Severity.INFO,
                        message="ok",
                    ),
                    RobustnessCheckResult(
                        check_name="stability",
                        passed=True,
                        severity=Severity.INFO,
                        message="ok",
                    ),
                ),
            )

    def test_duplicate_skipped_check_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationRequest(
                model_id="m1",
                result=_model_result(),
                diagnostics=_diagnostics(),
                skipped_robustness_checks=(
                    SkippedRobustnessCheck(check_name="x", reason="r1"),
                    SkippedRobustnessCheck(check_name="x", reason="r2"),
                ),
            )

    def test_with_multiple_testing_correction(self) -> None:
        r = ModelValidationRequest(
            model_id="m1",
            result=_model_result(),
            diagnostics=_diagnostics(),
            multiple_testing_correction=MultipleTestingCorrectionReport(
                family=TestFamily.COEFFICIENT,
                correction_method=MultipleTestingCorrectionMethod.BONFERRONI,
                alpha=0.05,
            ),
        )
        assert r.multiple_testing_correction is not None


# ---------------------------------------------------------------------------
# ValidatedModelInterpretation / RejectedModelInterpretation
# ---------------------------------------------------------------------------
class TestInterpretations:
    def test_validated(self) -> None:
        v = ValidatedModelInterpretation(
            interpretation_id="i1",
            claim_level=ClaimLevel.EXPLANATORY,
            evidence_grade=EvidenceGrade.MODERATE,
            approved_wording="associated with",
        )
        assert v.causal_warnings == ()

    def test_rejected(self) -> None:
        r = RejectedModelInterpretation(
            interpretation_id="i1",
            attempted_claim_level=ClaimLevel.CAUSAL,
            rejection_reason_code="CAUSAL_BLOCKED",
            rejection_reason_message="causal claims are blocked in MVP",
            rejected_wording="X causes Y",
        )
        assert r.causal_warnings == ()


# ---------------------------------------------------------------------------
# ModelValidationReport
# ---------------------------------------------------------------------------
class TestModelValidationReport:
    def test_passed_with_validated(self) -> None:
        r = ModelValidationReport(
            request=_validation_request(),
            validated=(
                ValidatedModelInterpretation(
                    interpretation_id="i1",
                    claim_level=ClaimLevel.EXPLANATORY,
                    evidence_grade=EvidenceGrade.MODERATE,
                    approved_wording="associated with",
                ),
            ),
            overall_passed=True,
        )
        assert r.rejected == ()

    def test_failed_with_rejected(self) -> None:
        r = ModelValidationReport(
            request=_validation_request(),
            rejected=(
                RejectedModelInterpretation(
                    interpretation_id="i1",
                    attempted_claim_level=ClaimLevel.CAUSAL,
                    rejection_reason_code="CAUSAL_BLOCKED",
                    rejection_reason_message="blocked",
                    rejected_wording="X causes Y",
                ),
            ),
            overall_passed=False,
        )
        assert r.rejected[0].rejection_reason_code == "CAUSAL_BLOCKED"

    def test_overall_passed_false_with_no_explanation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationReport(
                request=_validation_request(),
                overall_passed=False,
            )

    def test_duplicate_interpretation_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelValidationReport(
                request=_validation_request(),
                validated=(
                    ValidatedModelInterpretation(
                        interpretation_id="i1",
                        claim_level=ClaimLevel.EXPLANATORY,
                        evidence_grade=EvidenceGrade.MODERATE,
                        approved_wording="x",
                    ),
                ),
                rejected=(
                    RejectedModelInterpretation(
                        interpretation_id="i1",
                        attempted_claim_level=ClaimLevel.CAUSAL,
                        rejection_reason_code="X",
                        rejection_reason_message="m",
                        rejected_wording="w",
                    ),
                ),
                overall_passed=False,
            )

    def test_naive_computed_at_normalized(self) -> None:
        r = ModelValidationReport(
            request=_validation_request(),
            overall_passed=True,
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.computed_at is not None
        assert r.computed_at.tzinfo is timezone.utc

    def test_with_causal_warnings(self) -> None:
        r = ModelValidationReport(
            request=_validation_request(),
            overall_passed=True,
            causal_warnings=(
                CausalWarning(
                    code="X",
                    severity=Severity.WARNING,
                    message="m",
                    attempted_claim_level=ClaimLevel.CAUSAL,
                    downgraded_to=ClaimLevel.EXPLANATORY,
                ),
            ),
        )
        assert len(r.causal_warnings) == 1

    def test_round_trip(self) -> None:
        r = ModelValidationReport(
            request=_validation_request(), overall_passed=True
        )
        assert ModelValidationReport.model_validate(
            r.model_dump(mode="json")
        ) == r


def test_validation_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.validation as validation_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by validation contracts: {leaked}"
