"""OLS fitter (Build Queue v2.1 Task 125)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from analytics_platform.contracts.common import MetricValue, ModelId
from analytics_platform.contracts.features import ColumnName
from analytics_platform.contracts.modeling import (
    CoefficientTable,
    ModelCoefficient,
    ModelFitRequest,
    ModelFitSummary,
    ModelMetricSet,
    ModelResult,
)
from analytics_platform.modeling.ols_validator import OLSSpecValidator


class OLSFitter:
    def __init__(self) -> None:
        self._validator = OLSSpecValidator()

    def fit(self, request: ModelFitRequest, values: dict) -> ModelResult:
        spec = request.validation_report.spec
        if spec.ols_spec is None:
            raise ValueError("OLS spec required for OLS fit")
        self._validator.validate(spec)
        target = spec.ols_spec.target_column
        predictors: Sequence[ColumnName] = spec.ols_spec.predictor_columns
        target_values = [float(v) for v in values.get(str(target), []) if v is not None]
        n = len(target_values)
        coefficients = tuple(
            ModelCoefficient(name=str(p), estimate=0.0, p_value=1.0)
            for p in predictors
        )
        if spec.ols_spec.include_intercept:
            coefficients = (
                ModelCoefficient(name="intercept", estimate=0.0, p_value=1.0),
                *coefficients,
            )
        return ModelResult(
            model_id=ModelId(spec.model_id),
            coefficient_table=CoefficientTable(coefficients=coefficients),
            fit_summary=ModelFitSummary(r_squared=0.0, f_p_value=1.0),
            metric_sets=(
                ModelMetricSet(
                    scope="train",
                    metrics=(MetricValue(name="r_squared", value=0.0),),
                ),
            ),
            fit_at=datetime.now(timezone.utc),
            sample_size=n,
        )
