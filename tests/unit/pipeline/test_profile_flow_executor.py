"""Tests for the profile flow executor (Build Queue v2.1 Task 104)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import AnalysisPlan, PipelineStageName
from analytics_platform.pipeline.profile_flow_executor import (
    ProfileFlowExecutor,
    StageResult,
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


class TestProfileFlowExecutor:
    def test_run_all_stages_succeed(self) -> None:
        plan = AnalysisPlan(
            plan_id="p1",
            datasets=(_handle(),),
            stages=(PipelineStageName.CONFIG_LOAD, PipelineStageName.DATASET_LOAD),
        )
        results = ProfileFlowExecutor().execute(plan)
        assert all(r.status == "succeeded" for r in results)
        assert len(results) == 2
