"""Tests for feature contracts (Build Queue v2.1 Tasks 28-31).

Covers:

- ``TargetSpec`` / ``TargetTask`` invariants
  (``positive_class`` only valid for CLASSIFICATION).
- ``FeatureSpec`` / ``ColumnRole`` re-export validation.
- ``SplitSpec`` invariants (strategy dependencies; fractions sum
  to <= 1.0).
- ``FeatureBuildRequest`` invariants (target not in features /
  exclusions; unique feature / exclusion column names).
- ``FeatureEligibilityReport`` invariants (target_present=False
  forbids eligible=True; eligible=False requires block_reason;
  missing_required_features forbids eligible=True; unique column
  names in each collection).
- ``MissingValueStrategy`` / ``EncodingStrategy`` /
  ``ScalingStrategy`` / ``PreprocessingFitScope`` validation.
- ``FeatureTransformationPlan`` invariants (per-feature-step
  column names unique).
- ``FeatureTransformationReport`` invariants (executed / skipped
  column names unique).
- ``FeatureMatrixRef`` / ``FeatureMatrixResult`` validation.
- ``RowsExcludedReport`` / ``ColumnsExcludedReport`` invariants
  (count <= total; reason breakdown uniqueness / non-negative
  counts; per-column reason uniqueness).
- ``LeakageRiskType`` / ``LeakageRisk`` /
  ``LeakageCheckRequest`` / ``LeakageCheckReport`` invariants
  (passed=False requires block_reason; flag consistency).

These tests intentionally avoid importing any heavy compute library
so that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.features import (
    ColumnsExcludedReport,
    ColumnRole,
    EncodingStrategy,
    FeatureBuildRequest,
    FeatureEligibilityReport,
    FeatureExclusionReason,
    FeatureMatrixRef,
    FeatureMatrixResult,
    FeatureSpec,
    FeatureTransformationPlan,
    FeatureTransformationReport,
    LeakageCheckReport,
    LeakageCheckRequest,
    LeakageRisk,
    LeakageRiskType,
    MissingValueStrategy,
    PreprocessingFitScope,
    RowsExcludedReport,
    ScalingStrategy,
    SplitSpec,
    SplitStrategy,
    TargetSpec,
    TargetTask,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _target() -> TargetSpec:
    return TargetSpec(column_name="amount", task=TargetTask.REGRESSION)


def _feature(name: str = "age") -> FeatureSpec:
    return FeatureSpec(column_name=name)


def _build_request() -> FeatureBuildRequest:
    return FeatureBuildRequest(
        dataset=_handle(),
        target=_target(),
        features=(_feature("age"), _feature("income")),
    )


# ---------------------------------------------------------------------------
# TargetSpec / TargetTask / ColumnRole
# ---------------------------------------------------------------------------
class TestTargetSpec:
    def test_regression(self) -> None:
        t = TargetSpec(column_name="amount", task=TargetTask.REGRESSION)
        assert t.positive_class is None

    def test_classification_requires_no_positive_class(self) -> None:
        t = TargetSpec(
            column_name="churn",
            task=TargetTask.CLASSIFICATION,
            positive_class="yes",
        )
        assert t.positive_class == "yes"

    def test_regression_with_positive_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TargetSpec(
                column_name="amount",
                task=TargetTask.REGRESSION,
                positive_class="yes",
            )

    def test_round_trip(self) -> None:
        t = _target()
        assert TargetSpec.model_validate(t.model_dump(mode="json")) == t


class TestTargetTask:
    def test_known_members(self) -> None:
        assert TargetTask.REGRESSION.value == "regression"
        assert TargetTask.CLASSIFICATION.value == "classification"
        assert TargetTask.MULTICLASS.value == "multiclass"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            TargetTask("ranking")  # type: ignore[arg-type]


class TestColumnRoleReExport:
    def test_known_members(self) -> None:
        assert ColumnRole.FEATURE.value == "feature"
        assert ColumnRole.TARGET.value == "target"
        assert ColumnRole.EXCLUSION.value == "exclusion"


# ---------------------------------------------------------------------------
# FeatureSpec
# ---------------------------------------------------------------------------
class TestFeatureSpec:
    def test_defaults(self) -> None:
        f = FeatureSpec(column_name="age")
        assert f.role is ColumnRole.FEATURE
        assert f.include_in_model is True
        assert f.required_for_eligibility is True

    def test_round_trip(self) -> None:
        f = _feature()
        assert FeatureSpec.model_validate(f.model_dump(mode="json")) == f


# ---------------------------------------------------------------------------
# SplitSpec
# ---------------------------------------------------------------------------
class TestSplitSpec:
    def test_defaults(self) -> None:
        s = SplitSpec()
        assert s.strategy is SplitStrategy.RANDOM
        assert s.holdout_fraction == 0.0

    def test_time_requires_time_column(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(strategy=SplitStrategy.TIME)

    def test_time_with_time_column_ok(self) -> None:
        s = SplitSpec(strategy=SplitStrategy.TIME, time_column="ts")
        assert s.time_column == "ts"

    def test_group_requires_group_column(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(strategy=SplitStrategy.GROUP)

    def test_stratified_requires_stratify_column(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(strategy=SplitStrategy.STRATIFIED)

    def test_random_with_time_column_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(strategy=SplitStrategy.RANDOM, time_column="ts")

    def test_random_with_group_column_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(strategy=SplitStrategy.RANDOM, group_column="g")

    def test_fractions_sum_le_1(self) -> None:
        SplitSpec(train_fraction=0.6, test_fraction=0.4)
        SplitSpec(train_fraction=0.5, validation_fraction=0.2, test_fraction=0.3)

    def test_fractions_sum_gt_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(train_fraction=0.7, test_fraction=0.5)

    def test_negative_holdout_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SplitSpec(holdout_fraction=-0.1)


# ---------------------------------------------------------------------------
# FeatureBuildRequest
# ---------------------------------------------------------------------------
class TestFeatureBuildRequest:
    def test_basic(self) -> None:
        r = _build_request()
        assert r.fit_scope is PreprocessingFitScope.TRAIN_ONLY

    def test_target_in_features_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureBuildRequest(
                dataset=_handle(),
                target=_target(),
                features=(_feature("amount"),),
            )

    def test_target_in_exclusions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureBuildRequest(
                dataset=_handle(),
                target=_target(),
                features=(_feature("age"),),
                exclusions=("amount",),
            )

    def test_duplicate_feature_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureBuildRequest(
                dataset=_handle(),
                target=_target(),
                features=(_feature("age"), _feature("age")),
            )

    def test_duplicate_exclusions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureBuildRequest(
                dataset=_handle(),
                target=_target(),
                features=(_feature("age"),),
                exclusions=("a", "a"),
            )


# ---------------------------------------------------------------------------
# FeatureEligibilityReport
# ---------------------------------------------------------------------------
class TestFeatureEligibilityReport:
    def test_eligible_no_block(self) -> None:
        r = FeatureEligibilityReport(target_present=True)
        assert r.eligible is True

    def test_missing_target_forbids_eligible(self) -> None:
        with pytest.raises(ValidationError):
            FeatureEligibilityReport(target_present=False, eligible=True, block_reason="x")

    def test_not_eligible_requires_block_reason(self) -> None:
        with pytest.raises(ValidationError):
            FeatureEligibilityReport(target_present=True, eligible=False)

    def test_eligible_forbids_block_reason(self) -> None:
        with pytest.raises(ValidationError):
            FeatureEligibilityReport(target_present=True, eligible=True, block_reason="x")

    def test_missing_required_features_forbids_eligible(self) -> None:
        with pytest.raises(ValidationError):
            FeatureEligibilityReport(
                target_present=True,
                eligible=True,
                missing_required_features=("a",),
            )

    def test_duplicate_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureEligibilityReport(
                target_present=True,
                eligible=False,
                block_reason="missing",
                excluded_features=("a", "a"),
            )

    def test_round_trip(self) -> None:
        r = FeatureEligibilityReport(target_present=True)
        assert FeatureEligibilityReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Preprocessing enums
# ---------------------------------------------------------------------------
class TestPreprocessingEnums:
    def test_missing_value_strategies(self) -> None:
        assert MissingValueStrategy.DROP_ROW.value == "drop_row"
        assert MissingValueStrategy.IMPUTE_MEAN.value == "impute_mean"
        assert MissingValueStrategy.ADD_MISSING_INDICATOR.value == "add_missing_indicator"

    def test_encoding_strategies(self) -> None:
        assert EncodingStrategy.ONE_HOT.value == "one_hot"
        assert EncodingStrategy.TARGET.value == "target"

    def test_scaling_strategies(self) -> None:
        assert ScalingStrategy.STANDARD.value == "standard"
        assert ScalingStrategy.MIN_MAX.value == "min_max"

    def test_preprocessing_fit_scope(self) -> None:
        assert PreprocessingFitScope.TRAIN_ONLY.value == "train_only"
        assert PreprocessingFitScope.TRAIN_AND_HOLDOUT.value == "train_and_holdout"


# ---------------------------------------------------------------------------
# FeatureTransformationPlan / Report
# ---------------------------------------------------------------------------
class TestFeatureTransformationPlan:
    def test_empty(self) -> None:
        p = FeatureTransformationPlan(plan_id="plan-1")
        assert p.per_feature_steps == ()

    def test_per_feature_steps(self) -> None:
        p = FeatureTransformationPlan(
            plan_id="plan-1",
            per_feature_steps=(
                (
                    "age",
                    MissingValueStrategy.IMPUTE_MEAN,
                    EncodingStrategy.ONE_HOT,
                    ScalingStrategy.STANDARD,
                ),
            ),
        )
        assert len(p.per_feature_steps) == 1

    def test_duplicate_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureTransformationPlan(
                plan_id="plan-1",
                per_feature_steps=(
                    ("age", MissingValueStrategy.NONE, EncodingStrategy.NONE, ScalingStrategy.NONE),
                    (
                        "age",
                        MissingValueStrategy.IMPUTE_MEAN,
                        EncodingStrategy.ONE_HOT,
                        ScalingStrategy.STANDARD,
                    ),
                ),
            )


class TestFeatureTransformationReport:
    def test_basic(self) -> None:
        r = FeatureTransformationReport(plan_id="plan-1")
        assert r.executed_steps == ()
        assert r.skipped_steps == ()

    def test_duplicate_executed_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureTransformationReport(
                plan_id="plan-1",
                executed_steps=(
                    ("age", MissingValueStrategy.NONE, EncodingStrategy.NONE, ScalingStrategy.NONE),
                    (
                        "age",
                        MissingValueStrategy.IMPUTE_MEAN,
                        EncodingStrategy.ONE_HOT,
                        ScalingStrategy.STANDARD,
                    ),
                ),
            )

    def test_duplicate_skipped_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureTransformationReport(
                plan_id="plan-1",
                skipped_steps=(("age", "r1"), ("age", "r2")),
            )


# ---------------------------------------------------------------------------
# FeatureMatrixRef / Result / Rows / Columns reports
# ---------------------------------------------------------------------------
class TestFeatureMatrix:
    def test_ref(self) -> None:
        m = FeatureMatrixRef(matrix_id="m1", dataset_id="d1")
        assert m.row_count is None

    def test_ref_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeatureMatrixRef(matrix_id="m1", dataset_id="d1", row_count=-1)

    def test_result(self) -> None:
        r = FeatureMatrixResult(matrix_ref=FeatureMatrixRef(matrix_id="m1", dataset_id="d1"))
        assert r.row_exclusions is None
        assert r.column_exclusions is None


class TestRowsExcludedReport:
    def test_basic(self) -> None:
        r = RowsExcludedReport()
        assert r.excluded_row_count is None

    def test_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowsExcludedReport(excluded_row_count=200, total_row_count=100)

    def test_duplicate_reasons_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowsExcludedReport(
                reason_breakdown=(
                    (FeatureExclusionReason.HIGH_MISSINGNESS, 1),
                    (FeatureExclusionReason.HIGH_MISSINGNESS, 2),
                ),
            )

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowsExcludedReport(
                reason_breakdown=((FeatureExclusionReason.HIGH_MISSINGNESS, -1),),
            )

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowsExcludedReport(excluded_ratio=1.5)


class TestColumnsExcludedReport:
    def test_basic(self) -> None:
        r = ColumnsExcludedReport()
        assert r.excluded_column_count is None

    def test_count_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnsExcludedReport(excluded_column_count=200, total_column_count=100)

    def test_duplicate_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnsExcludedReport(
                per_column_reason=(
                    ("x", FeatureExclusionReason.CONSTANT_COLUMN),
                    ("x", FeatureExclusionReason.HIGH_MISSINGNESS),
                ),
            )

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnsExcludedReport(excluded_ratio=1.5)


# ---------------------------------------------------------------------------
# LeakageCheckRequest / Risk / Report
# ---------------------------------------------------------------------------
class TestLeakageRiskType:
    def test_known_members(self) -> None:
        assert LeakageRiskType.TARGET_AS_FEATURE.value == "target_as_feature"
        assert LeakageRiskType.POST_OUTCOME_PREDICTOR.value == "post_outcome_predictor"
        assert LeakageRiskType.TRAIN_TEST_CONTAMINATION.value == "train_test_contamination"
        assert LeakageRiskType.DUPLICATE_COLUMN.value == "duplicate_column"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            LeakageRiskType("snooping")  # type: ignore[arg-type]


class TestLeakageRisk:
    def test_basic(self) -> None:
        r = LeakageRisk(
            risk_type=LeakageRiskType.TARGET_AS_FEATURE,
            severity=Severity.CRITICAL,
            message="target column used as feature",
        )
        assert r.column_name is None

    def test_with_column(self) -> None:
        r = LeakageRisk(
            column_name="amount",
            risk_type=LeakageRiskType.TARGET_AS_FEATURE,
            severity=Severity.ERROR,
            message="target-as-feature",
            score=1.0,
        )
        assert r.score == 1.0

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LeakageRisk(
                risk_type=LeakageRiskType.TARGET_AS_FEATURE,
                severity=Severity.ERROR,
                message="x",
                score=1.5,
            )


class TestLeakageCheckRequest:
    def test_defaults(self) -> None:
        r = LeakageCheckRequest(feature_build=_build_request())
        assert r.check_train_test_contamination is True
        assert r.check_post_outcome_predictors is True
        assert r.fail_on_high_risk is True


class TestLeakageCheckReport:
    def test_passed_no_risks(self) -> None:
        r = LeakageCheckReport(
            request=LeakageCheckRequest(feature_build=_build_request()),
            passed=True,
        )
        assert r.passed is True
        assert r.risks == ()

    def test_passed_with_risks_ok(self) -> None:
        r = LeakageCheckReport(
            request=LeakageCheckRequest(feature_build=_build_request()),
            passed=True,
            risks=(
                LeakageRisk(
                    risk_type=LeakageRiskType.POST_OUTCOME_PREDICTOR,
                    severity=Severity.WARNING,
                    message="m",
                ),
            ),
        )
        assert len(r.risks) == 1

    def test_passed_with_block_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LeakageCheckReport(
                request=LeakageCheckRequest(feature_build=_build_request()),
                passed=True,
                block_reason="not actually blocked",
            )

    def test_failed_requires_block_reason(self) -> None:
        with pytest.raises(ValidationError):
            LeakageCheckReport(
                request=LeakageCheckRequest(feature_build=_build_request()),
                passed=False,
                risks=(
                    LeakageRisk(
                        risk_type=LeakageRiskType.TARGET_AS_FEATURE,
                        severity=Severity.CRITICAL,
                        message="m",
                    ),
                ),
            )

    def test_target_as_feature_flag_consistent(self) -> None:
        with pytest.raises(ValidationError):
            # Flag set but no corresponding risk
            LeakageCheckReport(
                request=LeakageCheckRequest(feature_build=_build_request()),
                passed=False,
                block_reason="x",
                target_as_feature_detected=True,
            )

    def test_train_test_contamination_flag_consistent(self) -> None:
        with pytest.raises(ValidationError):
            LeakageCheckReport(
                request=LeakageCheckRequest(feature_build=_build_request()),
                passed=False,
                block_reason="x",
                train_test_contamination_detected=True,
            )

    def test_flags_with_risks_ok(self) -> None:
        r = LeakageCheckReport(
            request=LeakageCheckRequest(feature_build=_build_request()),
            passed=False,
            block_reason="x",
            risks=(
                LeakageRisk(
                    column_name="amount",
                    risk_type=LeakageRiskType.TARGET_AS_FEATURE,
                    severity=Severity.CRITICAL,
                    message="m",
                ),
                LeakageRisk(
                    column_name="ts",
                    risk_type=LeakageRiskType.TRAIN_TEST_CONTAMINATION,
                    severity=Severity.ERROR,
                    message="m",
                ),
            ),
            target_as_feature_detected=True,
            train_test_contamination_detected=True,
        )
        assert r.target_as_feature_detected is True

    def test_round_trip(self) -> None:
        r = LeakageCheckReport(
            request=LeakageCheckRequest(feature_build=_build_request()),
            passed=True,
        )
        assert LeakageCheckReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_features_contracts_do_not_import_heavy_libs() -> None:
    """Importing the features contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.features as features_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by features contracts: {leaked}"
