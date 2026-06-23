"""Tests for the catalog dataset registry and lineage store (Build Queue v2.1 Tasks 87-88)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

import pytest

from analytics_platform.catalog import (
    DatasetAlreadyRegistered,
    DatasetRegistry,
    DatasetRegistryError,
    LineageStore,
    LineageStoreError,
    RegistrationOutcome,
    get_dataset_registry,
    get_lineage_store,
    record_lineage,
    register_load_result,
)
from analytics_platform.contracts.common import (
    ArtifactId,
    DatasetId,
    ExecutionStatus,
    LineageId,
    RunId,
    Severity,
    StageId,
)
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetFingerprint,
    DatasetHandle,
    DatasetLoadRequest,
    DatasetLoadResult,
    DatasetMaterializationStatus,
    DatasetRef,
    DatasetRole,
    IngestionReport,
    SourceFileMetadata,
    StorageBackend,
)
from analytics_platform.contracts.lineage import (
    DerivedDatasetRef,
    LineageOperationType,
    LineageRecord,
    SourceDatasetRef,
    TransformationRef,
)


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


def _fingerprint(content_hash: str = "abc123") -> DatasetFingerprint:
    return DatasetFingerprint(
        algorithm="sha256",
        content_hash=content_hash,
        source=SourceFileMetadata(uri="/tmp/d1.parquet", size_bytes=1024),
        computed_at=datetime(2026, 6, 20, 0, 0, tzinfo=UTC),
        row_count=10,
    )


def _ingestion() -> IngestionReport:
    return IngestionReport(
        detected_format=DatasetFormat.PARQUET,
        requested_format=DatasetFormat.PARQUET,
        rows_read=10,
        bytes_read=1024,
        fingerprint=_fingerprint(),
        source=SourceFileMetadata(uri="/tmp/d1.parquet", size_bytes=1024),
    )


def _handle(
    dataset_id: str = "d1",
    *,
    source_uri: str = "/tmp/d1.parquet",
    name: str | None = None,
    role: DatasetRole = DatasetRole.SOURCE,
    fingerprint_content_hash: str = "abc123",
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> DatasetHandle:
    return DatasetHandle(
        dataset_id=DatasetId(dataset_id),
        dataset_ref=DatasetRef(f"ds-{dataset_id}"),
        name=name or dataset_id,
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
        source_uri=source_uri,
        fingerprint=_fingerprint(fingerprint_content_hash),
        row_count_estimate=10,
        role=role,
        run_id=run_id,
        stage_id=stage_id,
    )


def _load_result(
    *,
    dataset_id: str = "d1",
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    handle: DatasetHandle | None = None,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> DatasetLoadResult:
    # Non-SUCCEEDED status forbids a handle (contract validator).
    # Use a synthetic handle-with-no-source when the caller wants
    # to exercise a SUCCEEDED load result.
    if status is not ExecutionStatus.SUCCEEDED:
        return DatasetLoadResult(
            request=DatasetLoadRequest(
                source_uri="/tmp/d1.parquet",
                format=DatasetFormat.PARQUET,
            ),
            status=status,
            handle=None,
            ingestion=_ingestion(),
            run_id=run_id,
            stage_id=stage_id,
        )
    if handle is None:
        handle = _handle(dataset_id=dataset_id, run_id=run_id, stage_id=stage_id)
    return DatasetLoadResult(
        request=DatasetLoadRequest(
            source_uri=handle.source_uri or "/tmp/d1.parquet",
            format=handle.format,
        ),
        status=status,
        handle=handle,
        ingestion=_ingestion(),
        run_id=run_id,
        stage_id=stage_id,
    )


def _lineage_record(
    lineage_id: str = "lin-1",
    *,
    operation: LineageOperationType = LineageOperationType.LOAD,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
    dataset_id: str = "d1",
) -> LineageRecord:
    transformation = TransformationRef(
        transformation_id="t-1",
        operation=operation,
        code=None,
        stage_id=stage_id,
        run_id=run_id,
    )
    derived = DerivedDatasetRef(
        dataset_id=DatasetId(dataset_id),
        dataset_ref=DatasetRef(f"ds-{dataset_id}"),
        fingerprint="abc123",
    )
    return LineageRecord(
        lineage_id=LineageId(lineage_id),
        operation=operation,
        sources=(
            SourceDatasetRef(
                dataset_id=DatasetId(dataset_id),
                dataset_ref=DatasetRef(f"ds-{dataset_id}"),
                fingerprint="abc123",
            ),
        ),
        transformation=transformation,
        derived=derived,
        recorded_at=datetime(2026, 6, 20, 0, 0, tzinfo=UTC),
        run_id=run_id,
        stage_id=stage_id,
    )


@pytest.fixture
def fresh_registry() -> DatasetRegistry:
    return DatasetRegistry()


@pytest.fixture
def fresh_lineage() -> LineageStore:
    return LineageStore()


@pytest.fixture
def clean_singletons() -> Iterable[None]:
    """Reset the module-level singletons around a test."""
    reg = get_dataset_registry()
    lin = get_lineage_store()
    reg.reset()
    lin.reset()
    # Wire the singleton lineage store into the singleton registry
    # so the convenience helper exercises the integration path.
    reg._lineage_store = lin  # noqa: SLF001
    try:
        yield
    finally:
        reg.reset()
        lin.reset()


# ===========================================================================
# Task 87 — DatasetRegistry
# ===========================================================================
class TestDatasetRegistryRegister:
    def test_register_returns_typed_result(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        result = fresh_registry.register(_handle(), ingestion=_ingestion())
        assert result.handle.dataset_id == DatasetId("d1")
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.ingestion is not None

    def test_register_stamps_registered_at(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        result = fresh_registry.register(_handle(), ingestion=_ingestion())
        assert result.handle.registered_at is not None
        assert result.handle.registered_at.tzinfo is not None

    def test_register_preserves_existing_registered_at(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        existing = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        handle = _handle().model_copy(update={"registered_at": existing})
        result = fresh_registry.register(handle, ingestion=_ingestion())
        assert result.handle.registered_at == existing

    def test_register_then_get_returns_same_handle(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        handle = _handle()
        fresh_registry.register(handle, ingestion=_ingestion())
        looked = fresh_registry.get_handle(handle.dataset_id)
        assert looked.dataset_id == handle.dataset_id
        assert looked.source_uri == handle.source_uri

    def test_register_then_get_returns_result(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        handle = _handle()
        fresh_registry.register(handle, ingestion=_ingestion())
        result = fresh_registry.get(handle.dataset_id)
        assert result.handle.dataset_id == handle.dataset_id

    def test_get_unknown_raises(self, fresh_registry: DatasetRegistry) -> None:
        with pytest.raises(DatasetRegistryError) as ei:
            fresh_registry.get(DatasetId("missing"))
        assert ei.value.issue.code == "DATASET_REGISTRY_LOOKUP_MISS"

    def test_try_get_returns_none_for_unknown(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        assert fresh_registry.try_get(DatasetId("missing")) is None

    def test_get_handle_unknown_raises(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        with pytest.raises(DatasetRegistryError) as ei:
            fresh_registry.get_handle(DatasetId("missing"))
        assert ei.value.issue.code == "DATASET_REGISTRY_LOOKUP_MISS"

    def test_duplicate_register_raises(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.register(_handle(), ingestion=_ingestion())
        with pytest.raises(DatasetAlreadyRegistered) as ei:
            fresh_registry.register(_handle(), ingestion=_ingestion())
        assert ei.value.dataset_id == DatasetId("d1")
        assert ei.value.issue.code == "DATASET_ALREADY_REGISTERED"

    def test_replace_overwrites_existing(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.register(_handle(), ingestion=_ingestion())
        new_handle = _handle(fingerprint_content_hash="different")
        result = fresh_registry.replace(new_handle, ingestion=_ingestion())
        assert result.handle.fingerprint is not None
        assert result.handle.fingerprint.content_hash == "different"

    def test_replace_works_when_id_is_new(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.replace(_handle(dataset_id="d1"), ingestion=_ingestion())
        assert DatasetId("d1") in fresh_registry.list()

    def test_unregister_removes_entry(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.register(_handle(), ingestion=_ingestion())
        assert fresh_registry.unregister(DatasetId("d1")) is True
        assert fresh_registry.try_get(DatasetId("d1")) is None

    def test_unregister_unknown_returns_false(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        assert fresh_registry.unregister(DatasetId("missing")) is False

    def test_list_returns_sorted(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        for did in ("z", "a", "m"):
            fresh_registry.register(_handle(did), ingestion=_ingestion())
        assert fresh_registry.list() == [DatasetId("a"), DatasetId("m"), DatasetId("z")]

    def test_reset_clears_registry(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.register(_handle(), ingestion=_ingestion())
        fresh_registry.reset()
        assert fresh_registry.list() == []

    def test_register_threads_runtime_store(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        fresh_registry.register(_handle(), ingestion=_ingestion())
        from analytics_platform.datasets import lookup_dataset

        assert lookup_dataset(DatasetId("d1")).dataset_id == DatasetId("d1")


class TestDatasetRegistryWithLineage:
    def test_register_records_lineage(
        self, fresh_registry: DatasetRegistry, fresh_lineage: LineageStore
    ) -> None:
        registry = DatasetRegistry(lineage_store=fresh_lineage)
        registry.register(_handle(), ingestion=_ingestion())
        records = fresh_lineage.list()
        assert len(records) == 1
        assert records[0].operation is LineageOperationType.LOAD

    def test_register_assigns_lineage_id_to_result(
        self, fresh_registry: DatasetRegistry, fresh_lineage: LineageStore
    ) -> None:
        registry = DatasetRegistry(lineage_store=fresh_lineage)
        result = registry.register(_handle(), ingestion=_ingestion())
        assert result.lineage_id is not None
        # Look up the stored record by the id the registry returned.
        assert fresh_lineage.get(result.lineage_id).operation is LineageOperationType.LOAD

    def test_register_without_lineage_store_does_not_raise(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        result = fresh_registry.register(_handle(), ingestion=_ingestion())
        assert result.lineage_id is None

    def test_replace_records_lineage(
        self, fresh_registry: DatasetRegistry, fresh_lineage: LineageStore
    ) -> None:
        registry = DatasetRegistry(lineage_store=fresh_lineage)
        registry.register(_handle(), ingestion=_ingestion())
        registry.replace(_handle(fingerprint_content_hash="v2"), ingestion=_ingestion())
        records = fresh_lineage.list()
        assert len(records) == 2
        assert all(r.operation is LineageOperationType.LOAD for r in records)


class TestRegistrationOutcomeBundle:
    def test_register_load_result_returns_outcome(
        self, clean_singletons: Iterable[None]
    ) -> None:
        outcome = register_load_result(_load_result())
        assert isinstance(outcome, RegistrationOutcome)
        assert outcome.result.handle.dataset_id == DatasetId("d1")
        assert outcome.lineage_record is not None
        assert outcome.lineage_record.operation is LineageOperationType.LOAD

    def test_register_load_result_rejects_failed_status(
        self, clean_singletons: Iterable[None]
    ) -> None:
        with pytest.raises(DatasetRegistryError) as ei:
            register_load_result(
                _load_result(status=ExecutionStatus.FAILED)
            )
        assert ei.value.issue.code == "DATASET_LOAD_NOT_SUCCEEDED"

    def test_register_load_result_rejects_missing_handle(
        self, clean_singletons: Iterable[None]
    ) -> None:
        result = _load_result()
        result_no_handle = result.model_copy(update={"handle": None})
        with pytest.raises(DatasetRegistryError) as ei:
            register_load_result(result_no_handle)
        assert ei.value.issue.code == "DATASET_LOAD_NO_HANDLE"

    def test_register_load_result_uses_explicit_registry(
        self, fresh_registry: DatasetRegistry
    ) -> None:
        outcome = register_load_result(_load_result(), registry=fresh_registry)
        assert outcome.result.handle.dataset_id == DatasetId("d1")
        assert fresh_registry.try_get(DatasetId("d1")) is outcome.result

    def test_register_load_result_duplicate_raises(
        self, clean_singletons: Iterable[None]
    ) -> None:
        register_load_result(_load_result())
        with pytest.raises(DatasetAlreadyRegistered):
            register_load_result(_load_result())

    def test_register_load_result_threads_artifact_id(
        self, clean_singletons: Iterable[None]
    ) -> None:
        outcome = register_load_result(
            _load_result(), artifact_id=ArtifactId("art-1")
        )
        assert outcome.result.artifact_id == ArtifactId("art-1")


# ===========================================================================
# Task 88 — LineageStore
# ===========================================================================
class TestLineageStoreAppend:
    def test_append_stores_record(self, fresh_lineage: LineageStore) -> None:
        rec = _lineage_record()
        fresh_lineage.append(rec)
        assert fresh_lineage.get(rec.lineage_id) is rec

    def test_append_returns_record(self, fresh_lineage: LineageStore) -> None:
        rec = _lineage_record()
        assert fresh_lineage.append(rec) is rec

    def test_append_duplicate_raises(self, fresh_lineage: LineageStore) -> None:
        fresh_lineage.append(_lineage_record("dup"))
        with pytest.raises(LineageStoreError) as ei:
            fresh_lineage.append(_lineage_record("dup"))
        assert ei.value.issue.code == "LINEAGE_DUPLICATE_ID"

    def test_append_insertion_order_preserved(
        self, fresh_lineage: LineageStore
    ) -> None:
        for i in range(5):
            fresh_lineage.append(_lineage_record(f"lin-{i}"))
        ids = [r.lineage_id for r in fresh_lineage.list()]
        assert ids == [LineageId(f"lin-{i}") for i in range(5)]

    def test_extend_appends_in_order(self, fresh_lineage: LineageStore) -> None:
        fresh_lineage.extend(
            [_lineage_record("lin-a"), _lineage_record("lin-b")]
        )
        assert len(fresh_lineage) == 2

    def test_extend_propagates_first_duplicate(
        self, fresh_lineage: LineageStore
    ) -> None:
        fresh_lineage.append(_lineage_record("lin-x"))
        with pytest.raises(LineageStoreError):
            fresh_lineage.extend(
                [_lineage_record("lin-y"), _lineage_record("lin-x")]
            )


class TestLineageStoreRead:
    def test_get_unknown_raises(self, fresh_lineage: LineageStore) -> None:
        with pytest.raises(LineageStoreError) as ei:
            fresh_lineage.get(LineageId("missing"))
        assert ei.value.issue.code == "LINEAGE_LOOKUP_MISS"

    def test_try_get_returns_none_for_unknown(
        self, fresh_lineage: LineageStore
    ) -> None:
        assert fresh_lineage.try_get(LineageId("missing")) is None

    def test_records_for_run_filters(
        self, fresh_lineage: LineageStore
    ) -> None:
        run_a = RunId("run-a")
        run_b = RunId("run-b")
        fresh_lineage.append(_lineage_record("a", run_id=run_a))
        fresh_lineage.append(_lineage_record("b", run_id=run_b))
        fresh_lineage.append(_lineage_record("c", run_id=run_a))
        assert {r.lineage_id for r in fresh_lineage.records_for_run(run_a)} == {
            LineageId("a"),
            LineageId("c"),
        }

    def test_records_for_run_empty(
        self, fresh_lineage: LineageStore
    ) -> None:
        assert fresh_lineage.records_for_run(RunId("nothing")) == ()

    def test_snapshot_for_run_collects_stage_ids(
        self, fresh_lineage: LineageStore
    ) -> None:
        run = RunId("run-x")
        fresh_lineage.append(
            _lineage_record("a", run_id=run, stage_id=StageId("stage-1"))
        )
        fresh_lineage.append(
            _lineage_record("b", run_id=run, stage_id=StageId("stage-2"))
        )
        snap = fresh_lineage.snapshot_for_run(run, snapshot_id="snap-1")
        assert snap.snapshot_id == "snap-1"
        assert snap.run_id == run
        assert len(snap.records) == 2
        assert set(snap.stage_ids) == {StageId("stage-1"), StageId("stage-2")}

    def test_snapshot_for_run_requires_records(
        self, fresh_lineage: LineageStore
    ) -> None:
        with pytest.raises(LineageStoreError) as ei:
            fresh_lineage.snapshot_for_run(RunId("nope"))
        assert ei.value.issue.code == "LINEAGE_EMPTY_RUN"

    def test_snapshot_for_run_generates_id_when_omitted(
        self, fresh_lineage: LineageStore
    ) -> None:
        run = RunId("run-y")
        fresh_lineage.append(_lineage_record("z", run_id=run))
        snap = fresh_lineage.snapshot_for_run(run)
        assert snap.snapshot_id != ""

    def test_reset_clears_store(self, fresh_lineage: LineageStore) -> None:
        fresh_lineage.append(_lineage_record("x"))
        fresh_lineage.reset()
        assert len(fresh_lineage) == 0


class TestModuleHelpers:
    def test_record_lineage_appends_to_singleton(
        self, clean_singletons: Iterable[None]
    ) -> None:
        rec = _lineage_record("mod-1")
        returned = record_lineage(rec)
        assert returned is rec
        assert get_lineage_store().try_get(LineageId("mod-1")) is rec

    def test_get_dataset_registry_singleton(self) -> None:
        assert get_dataset_registry() is get_dataset_registry()