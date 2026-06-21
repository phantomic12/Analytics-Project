"""Tests for modeling contracts (Build Queue v2.1 Tasks 33-35)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    MetricValue,
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
    AssumptionCheckResult,
    CoefficientTable,
    ModelAssumptionDiagnostics,
    ModelCoefficient,
    ModelDataDiagnostics,
    ModelDiagnosticReport,
    ModelFamily,
    ModelFitRequest,
    ModelFitSummary,
    ModelInterpretationLimit,
    ModelMetricSet,
    ModelPurpose,
    ModelResult,
    ModelSpec,
    ModelSpecValidationReport,
    ModelStabilityDiagnostics,
    ModelType,
    OLSModelSpec,
    OverfittingCheckResult,
    TargetType,
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


def _feature_build() -> FeatureBuildRequest:
    return FeatureBuildRequest(
        dataset=_handle(),
        target=TargetSpec(column_name="amount", task=TargetTask.REGRESSION),
        features=(FeatureSpec(column_name="age"),),
        split=SplitSpec(),
    )


def _ols_spec() -> OLSModelSpec:
    return OLSModelSpec(
        target_column="amount",
        predictor_columns=("age", "income"),
    )


def _model_spec() -> ModelSpec:
    return ModelSpec(
        model_id="m1",
        model_type=ModelType.OLS,
        model_family=ModelFamily.LINEAR,
        target_type=TargetType.CONTINUOUS,
        ols_spec=_ols_spec(),
    )


def _passed_validation() -> ModelSpecValidationReport:
    return ModelSpecValidationReport(
        spec=_model_spec(),
        passed=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestEnums:
    def test_model_type_known_members(self) -> None:
        assert ModelType.OLS.value == "ols"
        assert ModelType.LOGISTIC.value == "logistic"

    def test_invalid_model_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            ModelType("xgboost")  # type: ignore[arg-type]

    def test_model_family_known_members(self) -> None:
        assert ModelFamily.LINEAR.value == "linear"
        assert ModelFamily.GLM.value == "glm"

    def test_model_purpose_known_members(self) -> None:
        assert ModelPurpose.DESCRIPTIVE.value == "descriptive"
        assert ModelPurpose.PREDICTIVE.value == "predictive"
        assert ModelPurpose.INFERENTIAL.value == "inferential"


# ---------------------------------------------------------------------------
# OLSModelSpec
# ---------------------------------------------------------------------------
class TestOLSModelSpec:
    def test_basic(self) -> None:
        s = _ols_spec()
        assert s.include_intercept is True

    def test_target_in_predictors_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OLSModelSpec(
                target_column="amount",
                predictor_columns=("age", "amount"),
            )

    def test_empty_predictors_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OLSModelSpec(target_column="amount", predictor_columns=())

    def test_duplicate_predictors_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OLSModelSpec(
                target_column="amount",
                predictor_columns=("age", "age"),
            )

    def test_round_trip(self) -> None:
        s = _ols_spec()
        assert OLSModelSpec.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# ModelSpec
# ---------------------------------------------------------------------------
class TestModelSpec:
    def test_basic(self) -> None:
        s = _model_spec()
        assert s.purpose is ModelPurpose.DESCRIPTIVE

    def test_ols_requires_ols_spec(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpec(
                model_id="m1",
                model_type=ModelType.OLS,
                model_family=ModelFamily.LINEAR,
                target_type=TargetType.CONTINUOUS,
            )

    def test_non_ols_forbids_ols_spec(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpec(
                model_id="m1",
                model_type=ModelType.LOGISTIC,
                model_family=ModelFamily.GLM,
                target_type=TargetType.BINARY,
                ols_spec=_ols_spec(),
            )


# ---------------------------------------------------------------------------
# ModelSpecValidationReport
# ---------------------------------------------------------------------------
class TestModelSpecValidationReport:
    def test_passed(self) -> None:
        r = _passed_validation()
        assert r.passed is True

    def test_passed_with_block_reasons_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpecValidationReport(
                spec=_model_spec(),
                passed=True,
                block_reasons=(("BLOCK", "blocked"),),
            )

    def test_failed_requires_block_reasons(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpecValidationReport(
                spec=_model_spec(),
                passed=False,
            )

    def test_passed_target_constant_true_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpecValidationReport(
                spec=_model_spec(),
                passed=True,
                target_constant=True,
            )

    def test_failed_with_block_reasons(self) -> None:
        r = ModelSpecValidationReport(
            spec=_model_spec(),
            passed=False,
            block_reasons=(("CONSTANT_TARGET", "target is constant"),),
        )
        assert len(r.block_reasons) == 1

    def test_duplicate_block_codes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpecValidationReport(
                spec=_model_spec(),
                passed=False,
                block_reasons=(
                    ("X", "first"),
                    ("X", "second"),
                ),
            )

    def test_sample_size_consistent(self) -> None:
        with pytest.raises(ValidationError):
            ModelSpecValidationReport(
                spec=_model_spec(),
                passed=False,
                block_reasons=(("SAMPLE", "too small"),),
                sample_size=10,
                min_sample_size=100,
            )

    def test_with_issues_and_warnings(self) -> None:
        r = _passed_validation()
        r2 = ModelSpecValidationReport(
            spec=_model_spec(),
            passed=False,
            block_reasons=(("X", "y"),),
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings_records=(WarningRecord(code="W", message="m"),),
        )
        assert len(r2.issues) == 1

    def test_round_trip(self) -> None:
        r = _passed_validation()
        assert ModelSpecValidationReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# ModelFitRequest
# ---------------------------------------------------------------------------
class TestModelFitRequest:
    def test_passed_no_override(self) -> None:
        r = ModelFitRequest(
            validation_report=_passed_validation(),
            feature_build=_feature_build(),
            execution_limits=_limits(),
        )
        assert r.explicit_override is False

    def test_failed_requires_override(self) -> None:
        with pytest.raises(ValidationError):
            ModelFitRequest(
                validation_report=ModelSpecValidationReport(
                    spec=_model_spec(),
                    passed=False,
                    block_reasons=(("X", "y"),),
                ),
                feature_build=_feature_build(),
                execution_limits=_limits(),
            )

    def test_failed_with_override_ok(self) -> None:
        r = ModelFitRequest(
            validation_report=ModelSpecValidationReport(
                spec=_model_spec(),
                passed=False,
                block_reasons=(("X", "y"),),
            ),
            feature_build=_feature_build(),
            execution_limits=_limits(),
            explicit_override=True,
            override_reason="manual review",
        )
        assert r.explicit_override is True

    def test_override_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            ModelFitRequest(
                validation_report=_passed_validation(),
                feature_build=_feature_build(),
                execution_limits=_limits(),
                explicit_override=True,
            )


# ---------------------------------------------------------------------------
# ModelCoefficient / CoefficientTable
# ---------------------------------------------------------------------------
class TestModelCoefficient:
    def test_basic(self) -> None:
        c = ModelCoefficient(name="age", estimate=0.5)
        assert c.standard_error is None

    def test_p_value_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ModelCoefficient(name="age", estimate=0.5, p_value=1.5)


class TestCoefficientTable:
    def test_basic(self) -> None:
        t = CoefficientTable(
            coefficients=(
                ModelCoefficient(name="intercept", estimate=1.0),
                ModelCoefficient(name="age", estimate=0.5),
            )
        )
        assert len(t.coefficients) == 2

    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CoefficientTable(
                coefficients=(
                    ModelCoefficient(name="age", estimate=0.5),
                    ModelCoefficient(name="age", estimate=0.7),
                )
            )


# ---------------------------------------------------------------------------
# ModelFitSummary
# ---------------------------------------------------------------------------
class TestModelFitSummary:
    def test_basic(self) -> None:
        s = ModelFitSummary(r_squared=0.5, adjusted_r_squared=0.4)
        assert s.f_statistic is None

    def test_negative_residual_std_error_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelFitSummary(residual_std_error=-0.1)

    def test_p_value_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ModelFitSummary(f_p_value=1.5)


# ---------------------------------------------------------------------------
# ModelMetricSet
# ---------------------------------------------------------------------------
class TestModelMetricSet:
    def test_basic(self) -> None:
        s = ModelMetricSet(
            metrics=(MetricValue(name="r_squared", value=0.5),),
            scope="train",
        )
        assert s.scope == "train"

    def test_duplicate_metric_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelMetricSet(
                metrics=(
                    MetricValue(name="r_squared", value=0.5),
                    MetricValue(name="r_squared", value=0.6),
                )
            )


# ---------------------------------------------------------------------------
# ModelResult
# ---------------------------------------------------------------------------
class TestModelResult:
    def test_basic(self) -> None:
        r = ModelResult(
            model_id="m1",
            coefficient_table=CoefficientTable(
                coefficients=(ModelCoefficient(name="intercept", estimate=1.0),)
            ),
        )
        assert r.metric_sets == ()

    def test_metric_set_scopes_unique(self) -> None:
        with pytest.raises(ValidationError):
            ModelResult(
                model_id="m1",
                coefficient_table=CoefficientTable(),
                metric_sets=(
                    ModelMetricSet(metrics=(), scope="train"),
                    ModelMetricSet(metrics=(), scope="train"),
                ),
            )

    def test_naive_fit_at_normalized(self) -> None:
        r = ModelResult(
            model_id="m1",
            coefficient_table=CoefficientTable(),
            fit_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.fit_at is not None
        assert r.fit_at.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        r = ModelResult(
            model_id="m1",
            coefficient_table=CoefficientTable(
                coefficients=(ModelCoefficient(name="x", estimate=1.0),)
            ),
        )
        assert ModelResult.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
class TestAssumptionCheckResult:
    def test_basic(self) -> None:
        c = AssumptionCheckResult(
            name="normality",
            passed=True,
            severity=Severity.INFO,
            message="ok",
        )
        assert c.passed is True

    def test_p_value_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AssumptionCheckResult(
                name="n", passed=True, severity=Severity.INFO, message="m", p_value=1.5
            )


class TestModelAssumptionDiagnostics:
    def test_basic(self) -> None:
        d = ModelAssumptionDiagnostics()
        assert d.any_severe_violation is False

    def test_any_severe_violation_true(self) -> None:
        d = ModelAssumptionDiagnostics(
            checks=(
                AssumptionCheckResult(name="n", passed=False, severity=Severity.ERROR, message="m"),
            ),
            any_severe_violation=True,
        )
        assert d.any_severe_violation is True

    def test_any_severe_violation_consistent_with_checks(self) -> None:
        # True requires at least one non-passed ERROR/CRITICAL check
        with pytest.raises(ValidationError):
            ModelAssumptionDiagnostics(
                checks=(
                    AssumptionCheckResult(
                        name="n", passed=True, severity=Severity.ERROR, message="m"
                    ),
                ),
                any_severe_violation=True,
            )
        # computed but flag False
        with pytest.raises(ValidationError):
            ModelAssumptionDiagnostics(
                checks=(
                    AssumptionCheckResult(
                        name="n", passed=False, severity=Severity.ERROR, message="m"
                    ),
                ),
            )

    def test_check_names_unique(self) -> None:
        with pytest.raises(ValidationError):
            ModelAssumptionDiagnostics(
                checks=(
                    AssumptionCheckResult(
                        name="n", passed=True, severity=Severity.INFO, message="m"
                    ),
                    AssumptionCheckResult(
                        name="n", passed=True, severity=Severity.INFO, message="m2"
                    ),
                ),
            )


class TestModelDataDiagnostics:
    def test_basic(self) -> None:
        d = ModelDataDiagnostics(max_vif=2.5)
        assert d.high_vif_predictors == ()

    def test_duplicate_high_vif_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelDataDiagnostics(high_vif_predictors=("age", "age"))


class TestOverfittingCheckResult:
    def test_basic(self) -> None:
        c = OverfittingCheckResult(
            check_type="train_test_r2_gap",
            passed=True,
            severity=Severity.INFO,
            message="ok",
        )
        assert c.passed is True


class TestModelStabilityDiagnostics:
    def test_basic(self) -> None:
        d = ModelStabilityDiagnostics()
        assert d.any_severe_overfitting is False

    def test_duplicate_check_types_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelStabilityDiagnostics(
                overfitting_checks=(
                    OverfittingCheckResult(
                        check_type="x",
                        passed=True,
                        severity=Severity.INFO,
                        message="m",
                    ),
                    OverfittingCheckResult(
                        check_type="x",
                        passed=True,
                        severity=Severity.INFO,
                        message="m2",
                    ),
                ),
            )

    def test_severe_overfitting_consistent(self) -> None:
        with pytest.raises(ValidationError):
            ModelStabilityDiagnostics(
                overfitting_checks=(
                    OverfittingCheckResult(
                        check_type="x",
                        passed=True,
                        severity=Severity.ERROR,
                        message="m",
                    ),
                ),
                any_severe_overfitting=True,
            )


class TestModelInterpretationLimit:
    def test_basic(self) -> None:
        l = ModelInterpretationLimit(code="X", severity=Severity.WARNING, message="m")
        assert l.downgrades_coefficient_interpretation is False


class TestModelDiagnosticReport:
    def test_basic(self) -> None:
        r = ModelDiagnosticReport(
            model_id="m1",
            assumptions=ModelAssumptionDiagnostics(),
            data_diagnostics=ModelDataDiagnostics(),
            stability=ModelStabilityDiagnostics(),
        )
        assert r.interpretation_limits == ()

    def test_downgrade_requires_severe_violation(self) -> None:
        with pytest.raises(ValidationError):
            ModelDiagnosticReport(
                model_id="m1",
                assumptions=ModelAssumptionDiagnostics(),  # no severe violation
                data_diagnostics=ModelDataDiagnostics(),
                stability=ModelStabilityDiagnostics(),
                interpretation_limits=(
                    ModelInterpretationLimit(
                        code="X",
                        severity=Severity.WARNING,
                        message="m",
                        downgrades_coefficient_interpretation=True,
                    ),
                ),
            )

    def test_duplicate_codes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelDiagnosticReport(
                model_id="m1",
                assumptions=ModelAssumptionDiagnostics(
                    checks=(
                        AssumptionCheckResult(
                            name="n", passed=False, severity=Severity.ERROR, message="m"
                        ),
                    ),
                    any_severe_violation=True,
                ),
                data_diagnostics=ModelDataDiagnostics(),
                stability=ModelStabilityDiagnostics(),
                interpretation_limits=(
                    ModelInterpretationLimit(
                        code="X",
                        severity=Severity.WARNING,
                        message="m",
                        downgrades_coefficient_interpretation=True,
                    ),
                    ModelInterpretationLimit(
                        code="X",
                        severity=Severity.WARNING,
                        message="m2",
                        downgrades_coefficient_interpretation=True,
                    ),
                ),
            )

    def test_naive_computed_at_normalized(self) -> None:
        r = ModelDiagnosticReport(
            model_id="m1",
            assumptions=ModelAssumptionDiagnostics(),
            data_diagnostics=ModelDataDiagnostics(),
            stability=ModelStabilityDiagnostics(),
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.computed_at is not None
        assert r.computed_at.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        r = ModelDiagnosticReport(
            model_id="m1",
            assumptions=ModelAssumptionDiagnostics(),
            data_diagnostics=ModelDataDiagnostics(),
            stability=ModelStabilityDiagnostics(),
        )
        assert ModelDiagnosticReport.model_validate(r.model_dump(mode="json")) == r


def test_modeling_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.modeling as modeling_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by modeling contracts: {leaked}"
