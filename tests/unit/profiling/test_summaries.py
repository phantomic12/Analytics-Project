"""Tests for the profiling summary stage (Build Queue v2.1 Task 94)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.profiling import (
    DatasetProfile,
    ProfileComputationMode,
)
from analytics_platform.profiling.summaries import (
    ProfilingSummaryComputer,
    ProfilingSummaryError,
    compute_summaries,
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


class TestProfilingSummaryComputer:
    def test_empty_data_raises(self) -> None:
        with pytest_raises(ProfilingSummaryError):
            compute_summaries({})

    def test_numeric_column_produces_distribution(self) -> None:
        profile = compute_summaries({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
        assert isinstance(profile, DatasetProfile)
        assert len(profile.column_profiles) == 1
        col = profile.column_profiles[0]
        assert col.numeric is not None
        assert col.numeric.distribution.min == 1.0
        assert col.numeric.distribution.max == 10.0
        assert col.numeric.distribution.mean == 5.5
        assert col.computation_mode is ProfileComputationMode.EXACT

    def test_missingness_counted(self) -> None:
        data = {"a": [1, None, 3, None]}
        profile = compute_summaries(data)
        col = profile.column_profiles[0]
        assert col.missingness is not None
        assert col.missingness.missing_count == 2
        assert col.missingness.missing_ratio == 0.5

    def test_constant_column_warns(self) -> None:
        profile = compute_summaries({"b": ["x", "x", "x", "x"]})
        assert len(profile.constant_column_warnings) == 1
        assert profile.constant_column_warnings[0].column_name == "b"

    def test_high_cardinality_warns(self) -> None:
        # 60 distinct values > 50
        data = {"a": [f"v{i}" for i in range(60)]}
        profile = compute_summaries(data)
        assert len(profile.high_cardinality_warnings) == 1
        warning = profile.high_cardinality_warnings[0]
        assert warning.distinct_count == 60

    def test_categorical_path_runs(self) -> None:
        profile = compute_summaries({"c": ["a", "b", "a", "b", "a"]})
        col = profile.column_profiles[0]
        assert col.categorical is not None
        assert col.categorical.most_frequent_value == "a"
        assert col.categorical.most_frequent_count == 3

    def test_datetime_path_runs(self) -> None:
        from datetime import datetime
        data = {"d": [datetime(2024, 1, 1), datetime(2024, 6, 1), datetime(2024, 12, 31)]}
        profile = compute_summaries(data)
        col = profile.column_profiles[0]
        assert col.datetime is not None
        assert col.datetime.distinct_count == 3

    def test_dataset_handle_default(self) -> None:
        profile = compute_summaries({"a": [1, 2, 3]})
        assert profile.dataset is not None

    def test_dataset_handle_overrides_default(self) -> None:
        profile = compute_summaries({"a": [1, 2, 3]}, dataset=_handle())
        assert profile.dataset.dataset_id == "d1"


def pytest_raises(exc_type):
    import pytest
    return pytest.raises(exc_type)
