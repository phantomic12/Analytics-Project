"""Dirty dataset profile integration test (Build Queue v2.1 Task 109)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.profiling.summaries import compute_summaries


def _read_csv(path: Path) -> dict:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    cols = rows[0].keys()
    return {col: [r.get(col) for r in rows] for col in cols}


class TestDirtyDatasetProfile:
    def test_profile_dirty_dataset_detects_issues(self) -> None:
        fixture = (
            Path(__file__).parent.parent / "fixtures" / "datasets" / "small_dirty.csv"
        )
        with fixture.open(newline="") as f:
            rows = list(csv.DictReader(f))
        data: dict = {
            col: [None if v == "" else v for v in (r.get(col) for r in rows)]
            for col in rows[0].keys()
        }
        handle = DatasetHandle(
            dataset_id="dirty",
            dataset_ref=DatasetRef("dirty-profile"),
            name="dirty dataset",
            format=DatasetFormat.CSV,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.REGISTERED,
        )
        profile = compute_summaries(data, dataset=handle)
        assert len(profile.column_profiles) > 0
        missings = [
            cp.missingness.missing_count
            for cp in profile.column_profiles
            if cp.missingness is not None
        ]
        assert any(count > 0 for count in missings)
