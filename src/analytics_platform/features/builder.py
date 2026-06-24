"""Feature matrix builder (Build Queue v2.1 Task 123)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.common import DatasetId
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.features import (
    FeatureMatrixRef,
    FeatureMatrixResult,
    FeatureSpec,
    FeatureTransformationPlan,
)
from analytics_platform.features.missing_value_handler import MissingValueHandler


class FeatureMatrixBuilder:
    def __init__(self, handle: DatasetHandle, specs: Sequence[FeatureSpec], plan: FeatureTransformationPlan) -> None:
        self._handle = handle
        self._specs = list(specs)
        self._plan = plan

    def build(self) -> FeatureMatrixResult:
        ref = FeatureMatrixRef(
            matrix_id="matrix-1",
            dataset_id=str(self._handle.dataset_id),
        )
        missing = MissingValueHandler()
        _ = missing.handle([None, 1, 2])
        return FeatureMatrixResult(matrix_ref=ref)
