"""Tests for the profile flow plan builder (Build Queue v2.1 Task 103)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import (
    PipelineExecutionMode,
    PipelineStageName,
)
from analytics_platform.pipeline.profile_flow_plan import (
    PROFILE_ONLY_STAGES,
    ProfileFlowPlanBuilder,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


class TestProfileFlowPlanBuilder:
    def test_build_returns_profile_only_plan(self) -> None:
        plan = ProfileFlowPlanBuilder().build(plan_id="p1", datasets=[_handle()])
        assert plan.execution_mode is PipelineExecutionMode.PROFILE_ONLY
        assert plan.stages == PROFILE_ONLY_STAGES
        assert PipelineStageName.DISTRIBUTION_PROFILING in plan.stages
