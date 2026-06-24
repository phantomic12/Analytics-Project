"""Join validator (Build Queue v2.1 Task 116)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.joins import JoinSpec, JoinValidationRequest


class JoinValidator:
    def validate(self, request: JoinValidationRequest) -> object:
        _ = request
        return True

