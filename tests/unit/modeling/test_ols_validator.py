"""Tests for the OLS spec validator (Build Queue v2.1 Task 124)."""

from __future__ import annotations

import pytest

from analytics_platform.contracts.common import ModelId
from analytics_platform.contracts.features import ColumnName
from analytics_platform.contracts.modeling import (
    ModelFamily,
    ModelPurpose,
    ModelSpec,
    ModelType,
    OLSModelSpec,
    TargetType,
)
from analytics_platform.modeling.ols_validator import OLSSpecValidator


def _valid_spec(target: str, predictors: tuple) -> ModelSpec:
    return ModelSpec(
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


class TestOLSSpecValidator:
    def test_valid_spec_passes(self) -> None:
        report = OLSSpecValidator().validate(_valid_spec("y", ("x1", "x2")))
        assert report.passed is True

    def test_target_in_predictors_rejects(self) -> None:
        # We need a spec where target is in predictors. Bypass
        # OLSModelSpec's own validator by constructing the ModelSpec
        # with a pre-built ols_spec via pydantic's model_construct.
        from pydantic import BaseModel

        class _Shim(BaseModel):
            target_column: ColumnName
            predictor_columns: tuple[ColumnName, ...]
            include_intercept: bool = True

        bad_ols = _Shim(
            target_column=ColumnName("y"),
            predictor_columns=(ColumnName("y"), ColumnName("x1")),
        )
        spec = ModelSpec.model_construct(
            model_id=ModelId("m1"),
            model_type=ModelType.OLS,
            model_family=ModelFamily.LINEAR,
            target_type=TargetType.CONTINUOUS,
            purpose=ModelPurpose.DESCRIPTIVE,
            ols_spec=bad_ols,
        )
        report = OLSSpecValidator().validate(spec)
        assert report.passed is False
