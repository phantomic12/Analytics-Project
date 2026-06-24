"""Profile flow plan builder (Build Queue v2.1 Task 103)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.pipeline import (
    AnalysisPlan,
    PipelineExecutionMode,
    PipelineFailurePolicy,
    PipelineStageName,
)

PROFILE_ONLY_STAGES: tuple[PipelineStageName, ...] = (
    PipelineStageName.CONFIG_LOAD,
    PipelineStageName.DATASET_LOAD,
    PipelineStageName.DATASET_REGISTER,
    PipelineStageName.SCHEMA_INFERENCE,
    PipelineStageName.SEMANTIC_ROLE_INFERENCE,
    PipelineStageName.SCHEMA_VALIDATION,
    PipelineStageName.DATA_QUALITY,
    PipelineStageName.DISTRIBUTION_PROFILING,
    PipelineStageName.DIAGNOSTIC_ASSOCIATION,
    PipelineStageName.REPORT_BUNDLE_ASSEMBLY,
    PipelineStageName.RUN_MANIFEST_WRITING,
    PipelineStageName.FILE_BASED_REGISTRY_WRITING,
)


class ProfileFlowPlanBuilder:
    def build(
        self,
        *,
        plan_id: str,
        datasets: Sequence[DatasetHandle] = (),
    ) -> AnalysisPlan:
        return AnalysisPlan(
            plan_id=plan_id,
            datasets=tuple(datasets),
            stages=PROFILE_ONLY_STAGES,
            execution_mode=PipelineExecutionMode.PROFILE_ONLY,
            failure_policy=PipelineFailurePolicy.FAIL_FAST,
        )

