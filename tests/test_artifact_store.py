"""Tests for the Parquet artifact store (Build Queue v2.1 Task 84)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from analytics_platform.contracts.artifacts import ArtifactHash
from analytics_platform.contracts.artifacts import (
    ArtifactHashAlgorithm,
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
    PersistedArtifact,
)
from analytics_platform.contracts.common import ArtifactRef
from analytics_platform.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(root_dir=str(tmp_path / "artifacts"))


@pytest.fixture
def lf() -> pl.LazyFrame:
    return pl.LazyFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


class TestArtifactStoreWriteRead:
    def test_write_polars_frame(self, store: ArtifactStore, lf: pl.LazyFrame) -> None:
        artifact = store.write_polars_frame(
            lf, kind="dataset", artifact_id="a1", file_name="orders.parquet"
        )
        assert isinstance(artifact, PersistedArtifact)
        assert artifact.artifact_id == "a1"
        assert artifact.kind == "dataset"
        assert artifact.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert len(artifact.hash.digest) == 64
        assert artifact.size_bytes is not None
        assert artifact.size_bytes > 0
        assert Path(artifact.location).exists()

    def test_write_then_read_frame(
        self, store: ArtifactStore, lf: pl.LazyFrame
    ) -> None:
        artifact = store.write_polars_frame(
            lf, kind="dataset", artifact_id="a1", file_name="x.parquet"
        )
        df = store.read_polars_frame(artifact)
        assert isinstance(df, pl.DataFrame)
        assert sorted(df["a"].to_list()) == [1, 2, 3]

    def test_read_nonexistent_raises(self, store: ArtifactStore) -> None:
        artifact = PersistedArtifact(
            artifact_id="missing",
            kind="dataset",
            location=str(store.root_dir / "missing" / "x.parquet"),
            hash=ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest="0" * 64,
            ),
            storage_policy=ArtifactStoragePolicy(
                medium=ArtifactStorageMedium.LOCAL_FS,
                retention=ArtifactRetention.PERSISTENT,
            ),
        )
        with pytest.raises(ArtifactStoreError) as ei:
            store.read_polars_frame(artifact)
        assert ei.value.issue.code == "ARTIFACT_NOT_FOUND"

    def test_write_bytes_round_trip(self, store: ArtifactStore) -> None:
        artifact = store.write_bytes(
            artifact_id="a1",
            kind="report",
            file_name="report.md",
            data=b"# hello\n",
        )
        assert store.exists(artifact)
        assert store.read_bytes(artifact) == b"# hello\n"

    def test_write_creates_subdir(self, store: ArtifactStore, lf: pl.LazyFrame) -> None:
        store.write_polars_frame(
            lf, kind="dataset", artifact_id="a1", file_name="x.parquet"
        )
        assert (store.root_dir / "a1").is_dir()


class TestArtifactStoreHash:
    def test_compute_content_hash_sha256(self, tmp_path: Path) -> None:
        path = tmp_path / "x.txt"
        path.write_bytes(b"hello")
        assert compute_content_hash(path) == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_compute_content_hash_unsupported_algo(self, tmp_path: Path) -> None:
        path = tmp_path / "x.txt"
        path.write_bytes(b"hello")
        with pytest.raises(ArtifactStoreError):
            compute_content_hash(path, algorithm="not-a-real-algo")


class TestArtifactStoreDelete:
    def test_delete_existing(
        self, store: ArtifactStore, lf: pl.LazyFrame
    ) -> None:
        artifact = store.write_polars_frame(
            lf, kind="dataset", artifact_id="a1", file_name="x.parquet"
        )
        assert store.exists(artifact) is True
        assert store.delete(artifact) is True
        assert store.exists(artifact) is False

    def test_delete_missing_idempotent(self, store: ArtifactStore) -> None:
        artifact = PersistedArtifact(
            artifact_id="missing",
            kind="dataset",
            location=str(store.root_dir / "missing" / "x.parquet"),
            hash=ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest="0" * 64,
            ),
            storage_policy=ArtifactStoragePolicy(
                medium=ArtifactStorageMedium.LOCAL_FS,
                retention=ArtifactRetention.PERSISTENT,
            ),
        )
        assert store.delete(artifact) is False


class TestArtifactStoreValidation:
    def test_invalid_artifact_id_rejected(
        self, store: ArtifactStore, lf: pl.LazyFrame
    ) -> None:
        with pytest.raises(ArtifactStoreError) as ei:
            store.write_polars_frame(
                lf, kind="dataset", artifact_id="../bad", file_name="x.parquet"
            )
        assert ei.value.issue.code == "ARTIFACT_INVALID_ID"

    def test_invalid_file_name_rejected(
        self, store: ArtifactStore, lf: pl.LazyFrame
    ) -> None:
        with pytest.raises(ArtifactStoreError) as ei:
            store.write_polars_frame(
                lf, kind="dataset", artifact_id="a1", file_name="a/b.parquet"
            )
        assert ei.value.issue.code == "ARTIFACT_INVALID_FILE_NAME"


class TestArtifactRefCompat:
    def test_exists_accepts_artifact_ref(
        self, store: ArtifactStore, lf: pl.LazyFrame
    ) -> None:
        artifact = store.write_polars_frame(
            lf, kind="dataset", artifact_id="a1", file_name="x.parquet"
        )
        # ``ArtifactRef`` only carries artifact_id / kind / uri;
        # ``exists`` only consults ``location`` (here the ``uri``
        # attribute is used). The contract ``ArtifactRef`` lives
        # in ``contracts.common``.
        ref = ArtifactRef(
            artifact_id=artifact.artifact_id,
            kind=artifact.kind,
            uri=artifact.location,
        )
        assert store.exists(ref) is True
