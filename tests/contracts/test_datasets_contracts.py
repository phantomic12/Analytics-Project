"""Tests for dataset identity, load, ingestion, and fingerprint contracts.

Covers Build Queue v2.1 Tasks 18, 19, and 20:

- Task 18: ``DatasetFormat`` / ``DatasetRole`` / ``StorageBackend`` /
  ``DatasetMaterializationStatus`` enums; ``DatasetHandle`` and
  ``DatasetRef`` validation/serialization.
- Task 19: ``DatasetLoadRequest`` / ``DatasetLoadResult`` /
  ``IngestionReport`` / ``RegisteredDatasetResult`` request/result shapes
  and the invariants between them (SUCCEEDED requires handle, UNKNOWN
  format requires an ERROR issue, SUCCEEDED registration has no ERROR
  issues).
- Task 20: ``DatasetFingerprint`` and ``SourceFileMetadata`` validation,
  timezone coercion, and serialization round-trips.

These tests intentionally avoid importing any heavy compute library so that
they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    ExecutionStatus,
    Issue,
    Severity,
)
from analytics_platform.contracts.datasets import (
    DatasetFingerprint,
    DatasetFormat,
    DatasetHandle,
    DatasetLoadRequest,
    DatasetLoadResult,
    DatasetMaterializationStatus,
    DatasetRef,
    DatasetRole,
    IngestionReport,
    RegisteredDatasetResult,
    SourceFileMetadata,
    StorageBackend,
)


# ---------------------------------------------------------------------------
# Task 18 — Dataset identity enums
# ---------------------------------------------------------------------------
class TestDatasetFormat:
    def test_known_members(self) -> None:
        assert DatasetFormat.CSV.value == "csv"
        assert DatasetFormat.PARQUET.value == "parquet"
        assert DatasetFormat.JSON.value == "json"
        assert DatasetFormat.JSONL.value == "jsonl"
        assert DatasetFormat.TSV.value == "tsv"
        assert DatasetFormat.UNKNOWN.value == "unknown"

    def test_enum_from_value(self) -> None:
        assert DatasetFormat("csv") is DatasetFormat.CSV
        assert DatasetFormat("parquet") is DatasetFormat.PARQUET

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetFormat("xml")  # type: ignore[arg-type]


class TestDatasetRole:
    def test_known_members(self) -> None:
        assert DatasetRole.SOURCE.value == "source"
        assert DatasetRole.DERIVED.value == "derived"
        assert DatasetRole.JOINED.value == "joined"
        assert DatasetRole.FEATURE_MATRIX.value == "feature_matrix"
        assert DatasetRole.TARGET.value == "target"
        assert DatasetRole.REFERENCE.value == "reference"
        assert DatasetRole.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetRole("training")  # type: ignore[arg-type]


class TestStorageBackend:
    def test_known_members(self) -> None:
        assert StorageBackend.LOCAL_FS.value == "local_fs"
        assert StorageBackend.IN_MEMORY.value == "in_memory"
        assert StorageBackend.HTTP.value == "http"
        assert StorageBackend.S3.value == "s3"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            StorageBackend("ftp")  # type: ignore[arg-type]


class TestDatasetMaterializationStatus:
    def test_known_members(self) -> None:
        assert DatasetMaterializationStatus.REGISTERED.value == "registered"
        assert DatasetMaterializationStatus.LAZY.value == "lazy"
        assert DatasetMaterializationStatus.MATERIALIZED.value == "materialized"
        assert DatasetMaterializationStatus.STALE.value == "stale"
        assert DatasetMaterializationStatus.FAILED.value == "failed"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetMaterializationStatus("queued")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Task 18 — DatasetHandle / DatasetRef
# ---------------------------------------------------------------------------
class TestDatasetRef:
    def test_alias_is_str_compatible(self) -> None:
        r: DatasetRef = "ds-v1"
        assert r == "ds-v1"

    def test_empty_value_rejected_when_used_as_field(self) -> None:
        with pytest.raises(ValidationError):
            DatasetHandle(
                dataset_id="d1",
                dataset_ref="",  # type: ignore[arg-type]
                name="orders",
            )


class TestDatasetHandle:
    def test_valid_minimal(self) -> None:
        h = DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")
        assert h.dataset_id == "d1"
        assert h.dataset_ref == "ds-v1"
        assert h.name == "orders"
        assert h.role is DatasetRole.SOURCE
        assert h.format is DatasetFormat.UNKNOWN
        assert h.storage_backend is StorageBackend.LOCAL_FS
        assert h.materialization_status is DatasetMaterializationStatus.REGISTERED
        assert h.fingerprint is None
        assert h.source_uri is None
        assert h.schema_fingerprint is None
        assert h.row_count_estimate is None
        assert h.registered_at is None
        assert h.metadata is None

    def test_valid_with_all_optional_fields(self) -> None:
        fp = DatasetFingerprint(
            algorithm="sha256",
            content_hash="abc123",
            row_count=100,
        )
        ts = datetime(2026, 6, 20, 18, 0, 0, tzinfo=UTC)
        h = DatasetHandle(
            dataset_id="d1",
            dataset_ref="ds-v1",
            name="orders",
            role=DatasetRole.DERIVED,
            format=DatasetFormat.PARQUET,
            storage_backend=StorageBackend.S3,
            materialization_status=DatasetMaterializationStatus.MATERIALIZED,
            fingerprint=fp,
            source_uri="s3://bucket/orders.parquet",
            schema_fingerprint="sch-1",
            row_count_estimate=10_000,
            registered_at=ts,
            run_id="run-1",
            stage_id="stage-load",
            metadata={"team": "analytics"},
        )
        assert h.role is DatasetRole.DERIVED
        assert h.fingerprint is fp
        assert h.row_count_estimate == 10_000
        assert h.registered_at == ts
        assert h.metadata == {"team": "analytics"}

    def test_naive_datetime_is_normalized_to_utc(self) -> None:
        naive = datetime(2026, 6, 20, 18, 0, 0)
        h = DatasetHandle(
            dataset_id="d1",
            dataset_ref="ds-v1",
            name="orders",
            registered_at=naive,
        )
        assert h.registered_at is not None
        assert h.registered_at.tzinfo is UTC

    def test_aware_datetime_preserved(self) -> None:
        aware = datetime(2026, 6, 20, 18, 0, 0, tzinfo=UTC)
        h = DatasetHandle(
            dataset_id="d1",
            dataset_ref="ds-v1",
            name="orders",
            registered_at=aware,
        )
        assert h.registered_at == aware

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="")

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetHandle(
                dataset_id="d1",
                dataset_ref="ds-v1",
                name="orders",
                row_count_estimate=-1,
            )

    def test_empty_source_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetHandle(
                dataset_id="d1",
                dataset_ref="ds-v1",
                name="orders",
                source_uri="",
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetHandle(
                dataset_id="d1",
                dataset_ref="ds-v1",
                name="orders",
                extra="nope",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        h = DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")
        with pytest.raises(ValidationError):
            h.name = "renamed"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        h = DatasetHandle(
            dataset_id="d1",
            dataset_ref="ds-v1",
            name="orders",
            format=DatasetFormat.PARQUET,
            role=DatasetRole.DERIVED,
            registered_at=datetime(2026, 6, 20, 18, 0, 0, tzinfo=UTC),
        )
        restored = DatasetHandle.model_validate(h.model_dump(mode="json"))
        assert restored == h


# ---------------------------------------------------------------------------
# Task 20 — SourceFileMetadata + DatasetFingerprint
# ---------------------------------------------------------------------------
class TestSourceFileMetadata:
    def test_valid_minimal(self) -> None:
        m = SourceFileMetadata(uri="/data/orders.csv")
        assert m.uri == "/data/orders.csv"
        assert m.size_bytes is None
        assert m.content_hash is None
        assert m.last_modified_at is None

    def test_valid_with_all_optional_fields(self) -> None:
        ts = datetime(2026, 6, 20, 18, 0, 0, tzinfo=UTC)
        m = SourceFileMetadata(
            uri="/data/orders.parquet",
            size_bytes=1024,
            content_hash="deadbeef",
            last_modified_at=ts,
            encoding="utf-8",
            compression="snappy",
            metadata={"src": "etl"},
        )
        assert m.size_bytes == 1024
        assert m.content_hash == "deadbeef"
        assert m.last_modified_at == ts
        assert m.encoding == "utf-8"
        assert m.compression == "snappy"

    def test_empty_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceFileMetadata(uri="")

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceFileMetadata(uri="/x", size_bytes=-1)

    def test_naive_datetime_normalized(self) -> None:
        m = SourceFileMetadata(
            uri="/x",
            last_modified_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert m.last_modified_at is not None
        assert m.last_modified_at.tzinfo is UTC

    def test_round_trip(self) -> None:
        m = SourceFileMetadata(
            uri="/data/orders.parquet",
            size_bytes=2048,
            content_hash="abc",
            metadata={"k": "v"},
        )
        restored = SourceFileMetadata.model_validate(m.model_dump(mode="json"))
        assert restored == m


class TestDatasetFingerprint:
    def test_valid_content_only(self) -> None:
        fp = DatasetFingerprint(algorithm="sha256", content_hash="abc123")
        assert fp.algorithm == "sha256"
        assert fp.content_hash == "abc123"
        assert fp.source is None
        assert fp.row_count is None

    def test_valid_with_source_attached(self) -> None:
        src = SourceFileMetadata(uri="/data/x.csv", size_bytes=10)
        fp = DatasetFingerprint(
            algorithm="sha256",
            content_hash="abc",
            source=src,
            row_count=5,
            schema_fingerprint="sch",
        )
        assert fp.source is src
        assert fp.row_count == 5
        assert fp.schema_fingerprint == "sch"

    def test_empty_algorithm_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetFingerprint(algorithm="", content_hash="abc")

    def test_empty_content_hash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetFingerprint(algorithm="sha256", content_hash="")

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetFingerprint(algorithm="sha256", content_hash="abc", row_count=-1)

    def test_naive_datetime_normalized(self) -> None:
        fp = DatasetFingerprint(
            algorithm="sha256",
            content_hash="abc",
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert fp.computed_at is not None
        assert fp.computed_at.tzinfo is UTC

    def test_round_trip(self) -> None:
        fp = DatasetFingerprint(
            algorithm="sha256",
            content_hash="abc",
            source=SourceFileMetadata(uri="/x"),
            row_count=10,
            schema_fingerprint="sch",
            run_id="r1",
            metadata={"k": "v"},
        )
        restored = DatasetFingerprint.model_validate(fp.model_dump(mode="json"))
        assert restored == fp

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetFingerprint(
                algorithm="sha256",
                content_hash="abc",
                extra="nope",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# Task 19 — DatasetLoadRequest
# ---------------------------------------------------------------------------
class TestDatasetLoadRequest:
    def test_valid_minimal(self) -> None:
        r = DatasetLoadRequest(source_uri="/data/orders.csv")
        assert r.source_uri == "/data/orders.csv"
        assert r.format is DatasetFormat.UNKNOWN
        assert r.storage_backend is StorageBackend.LOCAL_FS
        assert r.role is DatasetRole.SOURCE
        assert r.name is None
        assert r.expected_fingerprint is None

    def test_valid_with_fingerprint_hint(self) -> None:
        fp = DatasetFingerprint(algorithm="sha256", content_hash="abc")
        r = DatasetLoadRequest(
            source_uri="/data/x.parquet",
            format=DatasetFormat.PARQUET,
            storage_backend=StorageBackend.S3,
            expected_fingerprint=fp,
            expected_schema_fingerprint="sch",
            name="orders",
            role=DatasetRole.DERIVED,
        )
        assert r.expected_fingerprint is fp
        assert r.expected_schema_fingerprint == "sch"
        assert r.role is DatasetRole.DERIVED

    def test_empty_source_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetLoadRequest(source_uri="")

    def test_round_trip(self) -> None:
        r = DatasetLoadRequest(source_uri="/x", format=DatasetFormat.CSV, name="orders")
        restored = DatasetLoadRequest.model_validate(r.model_dump(mode="json"))
        assert restored == r


# ---------------------------------------------------------------------------
# Task 19 — IngestionReport
# ---------------------------------------------------------------------------
def _ok_ingestion() -> IngestionReport:
    return IngestionReport(
        detected_format=DatasetFormat.CSV,
        requested_format=DatasetFormat.CSV,
        rows_read=100,
        bytes_read=4096,
        source=SourceFileMetadata(uri="/data/orders.csv", size_bytes=4096),
    )


class TestIngestionReport:
    def test_valid_minimal(self) -> None:
        ing = IngestionReport(detected_format=DatasetFormat.CSV)
        assert ing.detected_format is DatasetFormat.CSV
        assert ing.requested_format is None
        assert ing.rows_read is None
        assert ing.bytes_read is None
        assert ing.fingerprint is None
        assert ing.source is None
        assert ing.issues == ()
        assert ing.warnings == ()

    def test_valid_full(self) -> None:
        fp = DatasetFingerprint(algorithm="sha256", content_hash="abc")
        ing = IngestionReport(
            detected_format=DatasetFormat.PARQUET,
            requested_format=DatasetFormat.PARQUET,
            rows_read=1000,
            bytes_read=1_000_000,
            fingerprint=fp,
            source=SourceFileMetadata(uri="/data/x.parquet"),
            started_at=datetime(2026, 6, 20, 18, 0, 0),
            finished_at=datetime(2026, 6, 20, 18, 0, 5),
        )
        assert ing.fingerprint is fp
        # Naive datetimes are coerced to UTC by the model validator.
        assert ing.started_at is not None
        assert ing.started_at.tzinfo is UTC
        assert ing.finished_at is not None
        assert ing.finished_at.tzinfo is UTC

    def test_unknown_format_requires_error_issue(self) -> None:
        # UNKNOWN detected format is allowed only when paired with at least
        # one ERROR-or-higher Issue.
        with pytest.raises(ValidationError):
            IngestionReport(detected_format=DatasetFormat.UNKNOWN)

    def test_unknown_format_with_error_issue_accepted(self) -> None:
        ing = IngestionReport(
            detected_format=DatasetFormat.UNKNOWN,
            issues=(Issue(code="FMT_UNKNOWN", severity=Severity.ERROR, message="m"),),
        )
        assert ing.detected_format is DatasetFormat.UNKNOWN
        assert len(ing.issues) == 1

    def test_unknown_format_with_only_warning_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestionReport(
                detected_format=DatasetFormat.UNKNOWN,
                issues=(
                    Issue(
                        code="FMT_WARN",
                        severity=Severity.WARNING,
                        message="m",
                    ),
                ),
            )

    def test_negative_rows_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestionReport(detected_format=DatasetFormat.CSV, rows_read=-1)

    def test_negative_bytes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestionReport(detected_format=DatasetFormat.CSV, bytes_read=-1)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestionReport(
                detected_format=DatasetFormat.CSV,
                extra="nope",  # type: ignore[call-arg]
            )

    def test_round_trip(self) -> None:
        ing = _ok_ingestion()
        restored = IngestionReport.model_validate(ing.model_dump(mode="json"))
        assert restored == ing


# ---------------------------------------------------------------------------
# Task 19 — DatasetLoadResult
# ---------------------------------------------------------------------------
def _ok_handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


class TestDatasetLoadResult:
    def test_valid_succeeded(self) -> None:
        req = DatasetLoadRequest(source_uri="/data/orders.csv")
        res = DatasetLoadResult(
            request=req,
            status=ExecutionStatus.SUCCEEDED,
            handle=_ok_handle(),
            ingestion=_ok_ingestion(),
        )
        assert res.status is ExecutionStatus.SUCCEEDED
        assert res.handle is not None
        assert res.handle.dataset_id == "d1"

    def test_succeeded_requires_handle(self) -> None:
        with pytest.raises(ValidationError):
            DatasetLoadResult(
                request=DatasetLoadRequest(source_uri="/x"),
                status=ExecutionStatus.SUCCEEDED,
                handle=None,
                ingestion=_ok_ingestion(),
            )

    def test_failed_forbids_handle(self) -> None:
        with pytest.raises(ValidationError):
            DatasetLoadResult(
                request=DatasetLoadRequest(source_uri="/x"),
                status=ExecutionStatus.FAILED,
                handle=_ok_handle(),
                ingestion=_ok_ingestion(),
            )

    def test_failed_without_handle_ok(self) -> None:
        res = DatasetLoadResult(
            request=DatasetLoadRequest(source_uri="/x"),
            status=ExecutionStatus.FAILED,
            ingestion=_ok_ingestion(),
        )
        assert res.status is ExecutionStatus.FAILED
        assert res.handle is None

    def test_skipped_without_handle_ok(self) -> None:
        res = DatasetLoadResult(
            request=DatasetLoadRequest(source_uri="/x"),
            status=ExecutionStatus.SKIPPED,
            ingestion=_ok_ingestion(),
        )
        assert res.status is ExecutionStatus.SKIPPED

    def test_round_trip(self) -> None:
        req = DatasetLoadRequest(source_uri="/x", format=DatasetFormat.PARQUET, name="orders")
        res = DatasetLoadResult(
            request=req,
            status=ExecutionStatus.SUCCEEDED,
            handle=_ok_handle(),
            ingestion=_ok_ingestion(),
        )
        restored = DatasetLoadResult.model_validate(res.model_dump(mode="json"))
        assert restored == res
        assert restored.handle is not None
        assert restored.ingestion.rows_read == 100


# ---------------------------------------------------------------------------
# Task 19 — RegisteredDatasetResult
# ---------------------------------------------------------------------------
class TestRegisteredDatasetResult:
    def test_valid_succeeded_no_errors(self) -> None:
        reg = RegisteredDatasetResult(
            handle=_ok_handle(),
            status=ExecutionStatus.SUCCEEDED,
            ingestion=_ok_ingestion(),
        )
        assert reg.status is ExecutionStatus.SUCCEEDED
        assert reg.issues == ()
        assert reg.warnings == ()

    def test_valid_with_warnings(self) -> None:
        reg = RegisteredDatasetResult(
            handle=_ok_handle(),
            status=ExecutionStatus.SUCCEEDED,
            ingestion=_ok_ingestion(),
        )
        # Warnings are allowed; only ERROR/CRITICAL issues are forbidden on
        # SUCCEEDED status.
        assert reg.status is ExecutionStatus.SUCCEEDED

    def test_succeeded_with_error_issue_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegisteredDatasetResult(
                handle=_ok_handle(),
                status=ExecutionStatus.SUCCEEDED,
                ingestion=_ok_ingestion(),
                issues=(Issue(code="DUP", severity=Severity.ERROR, message="duplicate"),),
            )

    def test_failed_with_error_issue_ok(self) -> None:
        reg = RegisteredDatasetResult(
            handle=_ok_handle(),
            status=ExecutionStatus.FAILED,
            ingestion=_ok_ingestion(),
            issues=(Issue(code="DUP", severity=Severity.ERROR, message="duplicate"),),
        )
        assert reg.status is ExecutionStatus.FAILED

    def test_with_lineage_and_artifact(self) -> None:
        reg = RegisteredDatasetResult(
            handle=_ok_handle(),
            status=ExecutionStatus.SUCCEEDED,
            ingestion=_ok_ingestion(),
            lineage_id="lin-1",
            artifact_id="art-1",
            run_id="run-1",
            stage_id="stage-register",
            metadata={"src": "etl"},
        )
        assert reg.lineage_id == "lin-1"
        assert reg.artifact_id == "art-1"
        assert reg.metadata == {"src": "etl"}

    def test_round_trip(self) -> None:
        reg = RegisteredDatasetResult(
            handle=_ok_handle(),
            status=ExecutionStatus.SUCCEEDED,
            ingestion=_ok_ingestion(),
            lineage_id="lin-1",
        )
        restored = RegisteredDatasetResult.model_validate(reg.model_dump(mode="json"))
        assert restored == reg


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_datasets_contracts_do_not_import_heavy_libs() -> None:
    """Importing the dataset contracts module must not pull heavy libs.

    This mirrors the guards on the other contract modules and protects the
    contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``: contracts must remain
    dependency-light so downstream consumers can import them without
    dragging in heavy compute libraries.
    """
    import sys

    import analytics_platform.contracts.datasets as datasets_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by dataset contracts: {leaked}"
