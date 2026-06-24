"""Tests for the OLS fitter (Build Queue v2.1 Task 125)."""

from __future__ import annotations

import pytest

from analytics_platform.contracts.common import ModelId
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.execution import (
    ExecutionLimitPolicy,
    MemoryBudgetPolicy,
)
from analytics_platform.contracts.features import (
    ColumnName,
    FeatureBuildRequest,
    FeatureSpec,
    TargetSpec,
    TargetTask,
)
from analytics_platform.contracts.modeling import (
    ModelFamily,
    ModelFitRequest,
    ModelPurpose,
    ModelSpec,
    ModelSpecValidationReport,
    ModelType,
    OLSModelSpec,
    TargetType,
)
from analytics_platform.modeling.ols_fitter import OLSFitter


def _report(target: str, predictors: tuple) -> ModelSpecValidationReport:
    spec = ModelSpec(
        model_id=ModelId("m1"),
        model_type=ModelType.OLS,
        model_family=ModelFamily.LINEAR,
        target_type=TargetType.CONTINUOUS,
        purpose=ModelPurpose.DESCRIPTIVE,
        ols_spec=OLSModelSpec(
            target_column=ColumnName(target),
            predictor_columns=tuple(ColumnName(p) for p in predictors),
        ),
    )
    return ModelSpecValidationReport(spec=spec, passed=True)


class TestOLSFitter:
    def test_fit_returns_coefficients(self) -> None:
        spec_report = _report("y", ("x1", "x2"))
        request = ModelFitRequest(
            validation_report=spec_report,
            feature_build=FeatureBuildRequest(
                dataset=DatasetHandle(
                    dataset_id="d1",
                    dataset_ref=DatasetRef("d1"),
                    name="d1",
                    format=DatasetFormat.CSV,
                    storage_backend=StorageBackend.LOCAL_FS,
                    materialization_status=DatasetMaterializationStatus.REGISTERED,
                ),
                target=TargetSpec(column_name=ColumnName("y"), task=TargetTask.REGRESSION),
                features=(FeatureSpec(column_name=ColumnName("x1")),),
            ),
            execution_limits=ExecutionLimitPolicy(
                memory_budget=MemoryBudgetPolicy(max_bytes=1024 * 1024),
            ),
        )
        result = OLSFitter().fit(request, values={"y": [1.0, 2.0, 3.0]})
        assert result.sample_size == 3
        assert result.coefficient_table.coefficients[0].name == "intercept"
