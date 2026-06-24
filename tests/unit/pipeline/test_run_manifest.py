"""Tests for the run manifest writer (Build Queue v2.1 Task 101)."""

from __future__ import annotations

import json
from pathlib import Path

from analytics_platform.contracts.common import RunId
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import AnalysisPlan, PipelineStageName, RunManifestRequest
from analytics_platform.pipeline.run_manifest import RunManifestWriter


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


class TestRunManifestWriter:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        plan = AnalysisPlan(plan_id="p1", datasets=(_handle(),), stages=(PipelineStageName.CONFIG_LOAD,))
        writer = RunManifestWriter()
        path = writer.write(
            RunManifestRequest(plan=plan, run_id=RunId("r1")), tmp_path
        )
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["plan"]["plan_id"] == "p1"
