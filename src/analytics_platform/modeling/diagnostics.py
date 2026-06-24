"""Model diagnostics (Build Queue v2.1 Task 126)."""

from __future__ import annotations

from analytics_platform.contracts.modeling import (
    ModelAssumptionDiagnostics,
    ModelDataDiagnostics,
    ModelDiagnosticReport,
    ModelResult,
    ModelStabilityDiagnostics,
)


class ModelDiagnosticBuilder:
    def build(self, result: ModelResult) -> ModelDiagnosticReport:
        return ModelDiagnosticReport(
            model_id=result.model_id,
            assumptions=ModelAssumptionDiagnostics(checks=()),
            data_diagnostics=ModelDataDiagnostics(),
            stability=ModelStabilityDiagnostics(overfitting_checks=()),
        )
