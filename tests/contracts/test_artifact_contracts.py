"""Tests for artifact persistence contracts (Build Queue v2.1 Task 15).

Covers ``ArtifactHash``, ``ArtifactStoragePolicy``, ``PersistedArtifact``, and
``DatasetArtifactRef``: validation, defaults, serialization round-trips,
required artifact-ref fields (path/location, type/kind, hash, producer, storage
policy), rejection of missing/invalid metadata, surface guards against raw
dataframe-like fields, and an import-weight guard. These tests avoid heavy
compute libraries and do not implement cache, visuals, dataset, IO, catalog,
reporting, registry, or runtime artifact store behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactHashAlgorithm,
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
    DatasetArtifactRef,
    PersistedArtifact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash() -> ArtifactHash:
    return ArtifactHash(
        algorithm=ArtifactHashAlgorithm.SHA256,
        digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )


def _policy(medium: ArtifactStorageMedium = ArtifactStorageMedium.LOCAL_FS) -> ArtifactStoragePolicy:
    return ArtifactStoragePolicy(medium=medium)


# ---------------------------------------------------------------------------
# ArtifactHashAlgorithm / ArtifactHash
# ---------------------------------------------------------------------------
class TestArtifactHashAlgorithm:
    def test_known_members(self) -> None:
        assert ArtifactHashAlgorithm.SHA256.value == "sha256"
        assert ArtifactHashAlgorithm.SHA1.value == "sha1"
        assert ArtifactHashAlgorithm.BLAKE3.value == "blake3"
        assert ArtifactHashAlgorithm.XXHASH.value == "xxhash"
        assert ArtifactHashAlgorithm.IDENTITY.value == "identity"

    def test_enum_from_value(self) -> None:
        assert ArtifactHashAlgorithm("sha256") is ArtifactHashAlgorithm.SHA256

    def test_serializes_as_plain_string(self) -> None:
        assert ArtifactHashAlgorithm.SHA256 == "sha256"


class TestArtifactHash:
    def test_valid(self) -> None:
        h = _hash()
        assert h.algorithm is ArtifactHashAlgorithm.SHA256
        assert len(h.digest) == 64
        assert h.digest_size_bytes is None

    def test_with_digest_size(self) -> None:
        h = ArtifactHash(algorithm=ArtifactHashAlgorithm.SHA256, digest="abc", digest_size_bytes=32)
        assert h.digest_size_bytes == 32

    def test_algorithm_string_coerced(self) -> None:
        h = ArtifactHash(algorithm="sha256", digest="abc")  # type: ignore[arg-type]
        assert h.algorithm is ArtifactHashAlgorithm.SHA256

    @pytest.mark.parametrize("field", ["algorithm", "digest"])
    def test_missing_required_rejected(self, field: str) -> None:
        kwargs: dict[str, object] = {"algorithm": ArtifactHashAlgorithm.SHA256, "digest": "abc"}
        kwargs.pop(field)
        with pytest.raises(ValidationError):
            ArtifactHash(**kwargs)  # type: ignore[arg-type]

    def test_empty_digest_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactHash(algorithm=ArtifactHashAlgorithm.SHA256, digest="")

    def test_negative_digest_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256, digest="abc", digest_size_bytes=-1
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactHash(  # type: ignore[call-arg]
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest="abc",
                payload=b"bytes",  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        h = _hash()
        with pytest.raises(ValidationError):
            h.digest = "changed"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        h = ArtifactHash(
            algorithm=ArtifactHashAlgorithm.SHA256, digest="abc", digest_size_bytes=32
        )
        data = h.model_dump(mode="json")
        assert data["algorithm"] == "sha256"
        assert data["digest"] == "abc"
        restored = ArtifactHash.model_validate(data)
        assert restored == h
        assert restored.algorithm is ArtifactHashAlgorithm.SHA256


# ---------------------------------------------------------------------------
# ArtifactStoragePolicy
# ---------------------------------------------------------------------------
class TestArtifactStoragePolicy:
    def test_valid(self) -> None:
        p = _policy()
        assert p.medium is ArtifactStorageMedium.LOCAL_FS
        assert p.retention is ArtifactRetention.PERSISTENT
        assert p.mutable is False

    def test_defaults_are_restrictive(self) -> None:
        p = ArtifactStoragePolicy(medium=ArtifactStorageMedium.OBJECT_STORE)
        assert p.retention is ArtifactRetention.PERSISTENT
        assert p.mutable is False
        assert p.replication is None
        assert p.compression is None

    def test_with_all_fields(self) -> None:
        p = ArtifactStoragePolicy(
            medium=ArtifactStorageMedium.OBJECT_STORE,
            retention=ArtifactRetention.EPHEMERAL,
            mutable=True,
            replication=3,
            compression="zstd",
            metadata={"tier": "hot"},
        )
        assert p.retention is ArtifactRetention.EPHEMERAL
        assert p.mutable is True
        assert p.replication == 3
        assert p.compression == "zstd"

    def test_missing_medium_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactStoragePolicy()  # type: ignore[call-arg]

    def test_replication_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactStoragePolicy(medium=ArtifactStorageMedium.LOCAL_FS, replication=0)

    def test_empty_compression_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactStoragePolicy(medium=ArtifactStorageMedium.LOCAL_FS, compression="")

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactStoragePolicy(  # type: ignore[call-arg]
                medium=ArtifactStorageMedium.LOCAL_FS,
                dataframe=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        p = _policy()
        with pytest.raises(ValidationError):
            p.mutable = True  # type: ignore[misc]

    def test_round_trip(self) -> None:
        p = ArtifactStoragePolicy(
            medium=ArtifactStorageMedium.OBJECT_STORE,
            retention=ArtifactRetention.RUN_SCOPED,
            replication=2,
            compression="snappy",
        )
        data = p.model_dump(mode="json")
        assert data["medium"] == "object_store"
        assert data["retention"] == "run_scoped"
        restored = ArtifactStoragePolicy.model_validate(data)
        assert restored == p
        assert restored.medium is ArtifactStorageMedium.OBJECT_STORE
        assert restored.retention is ArtifactRetention.RUN_SCOPED


# ---------------------------------------------------------------------------
# PersistedArtifact
# ---------------------------------------------------------------------------
class TestPersistedArtifact:
    def _artifact(self, **overrides: object) -> PersistedArtifact:
        defaults: dict[str, object] = {
            "artifact_id": "art-1",
            "kind": "dataset",
            "location": "file:///tmp/art-1.parquet",
            "hash": _hash(),
            "storage_policy": _policy(),
        }
        defaults.update(overrides)
        return PersistedArtifact(**defaults)  # type: ignore[arg-type]

    def test_valid(self) -> None:
        a = self._artifact()
        assert a.artifact_id == "art-1"
        assert a.kind == "dataset"
        assert a.location.startswith("file://")
        assert a.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert a.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS

    def test_required_fields_present(self) -> None:
        a = self._artifact(
            producer="io-stage",
            producer_run_id="run-1",
            producer_stage_id="stage-io",
        )
        # path/location, type/kind, hash, producer, storage policy
        for attr in ("location", "kind", "hash", "storage_policy"):
            assert getattr(a, attr) is not None
        assert a.producer == "io-stage"
        assert a.producer_run_id == "run-1"
        assert a.producer_stage_id == "stage-io"

    @pytest.mark.parametrize("field", ["artifact_id", "kind", "location", "hash", "storage_policy"])
    def test_missing_required_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            self._artifact(**{field: None})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field,value", [("kind", ""), ("location", ""), ("size_bytes", -1)]
    )
    def test_invalid_values_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            self._artifact(**{field: value})

    def test_with_created_at(self) -> None:
        ts = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        a = self._artifact(created_at=ts)
        assert a.created_at == ts

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._artifact(payload=object())  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_frozen(self) -> None:
        a = self._artifact()
        with pytest.raises(ValidationError):
            a.kind = "report"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        a = self._artifact(
            producer="io-stage",
            producer_run_id="run-1",
            producer_stage_id="stage-io",
            size_bytes=1024,
            metadata={"origin": "task-15"},
        )
        data = a.model_dump(mode="json")
        assert data["kind"] == "dataset"
        assert data["hash"]["algorithm"] == "sha256"
        assert data["storage_policy"]["medium"] == "local_fs"
        assert data["size_bytes"] == 1024
        restored = PersistedArtifact.model_validate(data)
        assert restored == a
        assert restored.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert restored.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS


# ---------------------------------------------------------------------------
# DatasetArtifactRef
# ---------------------------------------------------------------------------
class TestDatasetArtifactRef:
    def _ref(self, **overrides: object) -> DatasetArtifactRef:
        defaults: dict[str, object] = {
            "dataset_id": "ds-1",
            "artifact_id": "art-1",
            "format": "parquet",
            "location": "file:///tmp/ds-1.parquet",
            "hash": _hash(),
            "storage_policy": _policy(),
        }
        defaults.update(overrides)
        return DatasetArtifactRef(**defaults)  # type: ignore[arg-type]

    def test_valid(self) -> None:
        r = self._ref()
        assert r.dataset_id == "ds-1"
        assert r.artifact_id == "art-1"
        assert r.kind == "dataset"
        assert r.format == "parquet"
        assert r.location.startswith("file://")
        assert r.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert r.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS

    def test_default_kind_is_dataset(self) -> None:
        assert self._ref().kind == "dataset"

    def test_required_fields_present(self) -> None:
        r = self._ref(
            producer="io-stage",
            producer_run_id="run-1",
            producer_stage_id="stage-io",
        )
        # path/location, type/kind, hash, producer, storage policy
        for attr in ("location", "kind", "hash", "storage_policy"):
            assert getattr(r, attr) is not None
        assert r.producer == "io-stage"
        assert r.producer_run_id == "run-1"
        assert r.producer_stage_id == "stage-io"

    @pytest.mark.parametrize(
        "field", ["dataset_id", "format", "location", "hash", "storage_policy"]
    )
    def test_missing_required_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            self._ref(**{field: None})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field,value",
        [("format", ""), ("rows", -1), ("columns", -1)],
    )
    def test_invalid_values_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            self._ref(**{field: value})

    def test_with_descriptors(self) -> None:
        r = self._ref(rows=1000, columns=32, schema_fingerprint="fp-abc")
        assert r.rows == 1000
        assert r.columns == 32
        assert r.schema_fingerprint == "fp-abc"

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._ref(dataframe=object())  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_frozen(self) -> None:
        r = self._ref()
        with pytest.raises(ValidationError):
            r.format = "csv"  # type: ignore[misc]

    def test_serializes(self) -> None:
        r = self._ref(producer="io-stage", producer_run_id="run-1", rows=500, columns=10)
        data = r.model_dump(mode="json")
        assert data["dataset_id"] == "ds-1"
        assert data["kind"] == "dataset"
        assert data["format"] == "parquet"
        assert data["hash"]["algorithm"] == "sha256"
        assert data["storage_policy"]["medium"] == "local_fs"
        assert data["rows"] == 500
        restored = DatasetArtifactRef.model_validate(data)
        assert restored == r
        assert restored.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert restored.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS


# ---------------------------------------------------------------------------
# Surface guards: no raw dataframe-like object fields
# ---------------------------------------------------------------------------
def test_artifact_hash_field_surface() -> None:
    assert set(ArtifactHash.model_fields) == {"algorithm", "digest", "digest_size_bytes"}


def test_artifact_storage_policy_field_surface() -> None:
    assert set(ArtifactStoragePolicy.model_fields) == {
        "medium", "retention", "mutable", "replication", "compression", "metadata"
    }


def test_persisted_artifact_field_surface() -> None:
    assert set(PersistedArtifact.model_fields) == {
        "artifact_id", "kind", "location", "hash", "storage_policy", "producer",
        "producer_run_id", "producer_stage_id", "created_at", "size_bytes", "metadata",
    }


def test_dataset_artifact_ref_field_surface() -> None:
    assert set(DatasetArtifactRef.model_fields) == {
        "dataset_id", "artifact_id", "kind", "format", "location", "hash",
        "storage_policy", "producer", "producer_run_id", "producer_stage_id",
        "rows", "columns", "schema_fingerprint", "created_at", "metadata",
    }


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_artifact_contracts_do_not_import_heavy_libs() -> None:
    """The artifact contracts module must not pull heavy compute libraries."""
    import sys

    import analytics_platform.contracts.artifacts as artifacts_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by artifact contracts: {leaked}"