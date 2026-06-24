"""Profile-only MVP checkpoint test (Build Queue v2.1 Task 108)."""

from __future__ import annotations

import os

import pytest

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import PipelineStageName
from analytics_platform.pipeline.profile_orchestrator import ProfileOrchestrator
from analytics_platform.pipeline.profile_flow_plan import ProfileFlowPlanBuilder


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="dirty",
        dataset_ref=DatasetRef("dirty-profile"),
        name="dirty dataset",
        format=DatasetFormat.CSV,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.REGISTERED,
    )


class TestProfileOnlySmoke:
    def test_profile_only_smoke_passes(self) -> None:
        builder = ProfileFlowPlanBuilder()
        plan = builder.build(
            plan_id="profile-only-smoke",
            datasets=[_handle()],
        )
        result = ProfileOrchestrator().run(plan, run_id="smoke-1")
        assert result.status.value == "succeeded"
        assert result.run_id == "smoke-1"
        assert PipelineStageName.DISTRIBUTION_PROFILING in plan.stages
