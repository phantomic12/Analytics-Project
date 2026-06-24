"""OLS spec validator (Build Queue v2.1 Task 124)."""

from __future__ import annotations

from analytics_platform.contracts.modeling import (
    ModelSpec,
    ModelSpecValidationReport,
    ModelType,
)


class OLSSpecValidator:
    def validate(self, spec: ModelSpec) -> ModelSpecValidationReport:
        errors: list[tuple[str, str]] = []
        if spec.model_type is ModelType.OLS and spec.ols_spec is None:
            errors.append(("ols_spec_missing", "OLS spec missing"))
        if spec.ols_spec is not None:
            ols = spec.ols_spec
            if not ols.predictor_columns:
                errors.append(("no_predictors", "OLS spec has no predictors"))
            if ols.target_column in ols.predictor_columns:
                errors.append(("target_in_predictors", "target column appears in predictors"))
        passed = not errors
        if passed:
            return ModelSpecValidationReport(spec=spec, passed=True)
        return ModelSpecValidationReport(spec=spec, passed=False, block_reasons=tuple(errors))
