"""Tests for the profile-only orchestrator (Build Queue v2.1 Task 105)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import AnalysisPlan, PipelineStageName
from analytics_platform.contracts.registry import RunStatus
from analytics_platform.pipeline.profile_orchestrator import ProfileOrchestrator


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


class TestProfileOrchestrator:
    def test_run_succeeds_for_plan(self) -> None:
        plan = AnalysisPlan(
            plan_id="p1",
            datasets=(_handle(),),
            stages=(PipelineStageName.CONFIG_LOAD,),
        )
        result = ProfileOrchestrator().run(plan, run_id="r1")
        assert result.status is RunStatus.SUCCEEDED
        assert result.run_id == "r1"
