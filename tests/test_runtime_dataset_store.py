"""Tests for the runtime dataset store (Build Queue v2.1 Task 85)."""

from __future__ import annotations

import pytest

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetId,
    DatasetMaterializationStatus,
    DatasetRole,
    StorageBackend,
)
from analytics_platform.datasets import (
    DatasetNotFound,
    RuntimeDatasetStore,
    list_datasets,
    lookup_dataset,
    register_dataset,
    try_lookup_dataset,
    unregister_dataset,
)


def _handle(
    dataset_id: str = "d1",
    *,
    source_uri: str = "/data/d1.parquet",
) -> DatasetHandle:
    return DatasetHandle(
        dataset_id=DatasetId(dataset_id),
        dataset_ref=f"ds-{dataset_id}",
        name=dataset_id,
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
        source_uri=source_uri,
        role=DatasetRole.SOURCE,
    )


@pytest.fixture
def fresh() -> RuntimeDatasetStore:
    return RuntimeDatasetStore()


class TestRuntimeDatasetStore:
    def test_register_and_get(self, fresh: RuntimeDatasetStore) -> None:
        handle = _handle()
        fresh.register(handle)
        assert fresh.get(handle.dataset_id) is handle

    def test_get_unknown_raises(self, fresh: RuntimeDatasetStore) -> None:
        with pytest.raises(DatasetNotFound) as ei:
            fresh.get(DatasetId("missing"))
        assert ei.value.issue.code == "DATASET_NOT_FOUND"

    def test_try_get_returns_none(self, fresh: RuntimeDatasetStore) -> None:
        assert fresh.try_get(DatasetId("missing")) is None

    def test_register_overwrites(self, fresh: RuntimeDatasetStore) -> None:
        h1 = _handle(dataset_id="d1", source_uri="/data/v1.parquet")
        h1b = _handle(dataset_id="d1", source_uri="/data/v2.parquet")
        fresh.register(h1)
        fresh.register(h1b)
        assert fresh.get(DatasetId("d1")) is h1b

    def test_lookup_by_artifact(self, fresh: RuntimeDatasetStore) -> None:
        h = _handle(source_uri="/data/a1.parquet")
        fresh.register(h)
        # ``source_uri`` ends with the artifact id; the helper
        # finds it.
        assert fresh.lookup_by_artifact("a1.parquet") is h
        assert fresh.lookup_by_artifact("missing.parquet") is None

    def test_unregister_removes(self, fresh: RuntimeDatasetStore) -> None:
        h = _handle()
        fresh.register(h)
        assert fresh.unregister(h.dataset_id) is True
        assert fresh.try_get(h.dataset_id) is None

    def test_unregister_unknown_is_false(self, fresh: RuntimeDatasetStore) -> None:
        assert fresh.unregister(DatasetId("missing")) is False

    def test_list_sorted(self, fresh: RuntimeDatasetStore) -> None:
        fresh.register(_handle(dataset_id="c"))
        fresh.register(_handle(dataset_id="a"))
        fresh.register(_handle(dataset_id="b"))
        assert fresh.list() == [DatasetId("a"), DatasetId("b"), DatasetId("c")]

    def test_clear_empties(self, fresh: RuntimeDatasetStore) -> None:
        fresh.register(_handle())
        fresh.clear()
        assert fresh.list() == []


class TestModuleLevelApi:
    def test_register_and_lookup(self) -> None:
        from analytics_platform.datasets import _STORE

        _STORE.clear()
        h = _handle(dataset_id="d1")
        register_dataset(h)
        try:
            assert lookup_dataset(DatasetId("d1")) is h
            assert try_lookup_dataset(DatasetId("d1")) is h
            assert DatasetId("d1") in list_datasets()
        finally:
            unregister_dataset(DatasetId("d1"))
