"""Tests for the dataset profiler (Build Queue v2.1 Task 96)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.profiling import DatasetProfile
from analytics_platform.profiling.profiler import (
    Profiler,
    ProfilerError,
    profile_dataset,
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


def pytest_raises(exc_type):
    import pytest
    return pytest.raises(exc_type)


class TestProfiler:
    def test_empty_data_raises(self) -> None:
        with pytest_raises(ProfilerError):
            profile_dataset(_handle(), {})

    def test_basic_profile(self) -> None:
        profile = profile_dataset(_handle(), {"a": [1, 2, 3, 4, 5]})
        assert isinstance(profile, DatasetProfile)
        assert profile.dataset.dataset_id == "d1"
        assert len(profile.column_profiles) == 1

    def test_class_api_matches_module(self) -> None:
        profiler = Profiler()
        profile = profiler.profile(_handle(), {"a": [1, 2, 3]})
        assert profile.column_profiles[0].numeric is not None
