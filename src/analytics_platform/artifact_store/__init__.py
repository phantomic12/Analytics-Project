"""Parquet artifact store (Build Queue v2.1 Task 84).

This module is the canonical Parquet-backed artifact store. It
owns the durable, on-disk representation of artifacts referenced
by :class:`analytics_platform.contracts.execution.MaterializationResult`
and the runtime dataset store (Task 85). The store uses Polars
for read/write (Parquet is Polars' native columnar format).

Per the architecture-test plan (section 5), the
``artifact_store`` module is a domain module and may import from
contracts, core, the backends registry (Task 83), and the
approved runtime libraries (Polars is approved).

Scope (Task 84):

- :class:`ArtifactStore`: the canonical Parquet-backed artifact
  store. Implements ``write`` / ``read`` / ``exists`` /
  ``delete`` for typed artifacts referenced by
  :class:`analytics_platform.contracts.artifacts.PersistedArtifact`.
- :func:`compute_content_hash`: helper that returns the SHA-256
  hex digest of a file's bytes.
- :class:`ArtifactStoreError`: typed exception carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactHashAlgorithm,
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
    PersistedArtifact,
)
from analytics_platform.contracts.common import ArtifactRef, Issue, Severity
from analytics_platform.core import (
    AnalyticsPlatformError,
    get_logger,
)

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl

__all__ = [
    "ArtifactStore",
    "ArtifactStoreError",
    "compute_content_hash",
]


_LOGGER = get_logger("artifact_store")


class ArtifactStoreError(AnalyticsPlatformError):
    """A typed artifact-store failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


def compute_content_hash(path: Path, *, algorithm: str = "sha256") -> str:
    """Return the hex digest of ``path``'s bytes using ``algorithm``.

    The function reads the file in bounded chunks so it works
    for arbitrarily large Parquet files. The default algorithm
    is ``sha256``; ``sha1`` and ``md5`` are accepted for legacy
    compatibility only.
    """
    if algorithm not in ("sha256", "sha1", "md5", "blake3", "xxhash"):
        raise ArtifactStoreError(
            _make_issue(
                code="ARTIFACT_HASH_ALGORITHM_UNSUPPORTED",
                message=f"Unsupported content-hash algorithm: {algorithm!r}",
            )
        )
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class ArtifactStore:
    """The canonical Parquet-backed artifact store.

    A :class:`ArtifactStore` is constructed with a
    ``root_dir`` under which every artifact is written. The
    store implements the standard CRUD operations plus a
    ``write_polars_frame`` shortcut that takes a Polars frame
    (the canonical in-process input from the Polars backend)
    and returns the typed :class:`PersistedArtifact`.

    Construction parameters:

    - ``root_dir``: directory under which artifacts live.
      Created lazily on first write.
    - ``medium``: storage medium label (defaults to
      :attr:`ArtifactStorageMedium.LOCAL_FS`).
    - ``retention``: retention class (defaults to
      :attr:`ArtifactRetention.PERSISTENT`).
    """

    def __init__(
        self,
        root_dir: str,
        *,
        medium: ArtifactStorageMedium = ArtifactStorageMedium.LOCAL_FS,
        retention: ArtifactRetention = ArtifactRetention.PERSISTENT,
    ) -> None:
        self._root_dir = Path(root_dir).expanduser().resolve(strict=False)
        self._medium = medium
        self._retention = retention

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    # -----------------------------------------------------------------
    # Polars shortcut
    # -----------------------------------------------------------------
    def write_polars_frame(
        self,
        frame: "pl.LazyFrame | pl.DataFrame",
        *,
        kind: str,
        artifact_id: str,
        file_name: str,
    ) -> PersistedArtifact:
        """Write a Polars frame as Parquet and return a typed
        :class:`PersistedArtifact`.

        The function creates the artifact's parent directory on
        demand and computes a real SHA-256 content hash for the
        written file. The ``kind`` and ``artifact_id`` are
        recorded on the artifact for downstream registry /
        manifest writers.
        """
        try:
            import polars as pl  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ArtifactStoreError(
                _make_issue(
                    code="POLARS_NOT_INSTALLED",
                    message=(
                        "Polars is required for the Parquet artifact "
                        f"store but is not installed: {exc}"
                    ),
                )
            ) from exc

        if not isinstance(frame, (pl.LazyFrame, pl.DataFrame)):
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_INVALID_FRAME",
                    message=(
                        "ArtifactStore.write_polars_frame expected a "
                        f"Polars frame, got {type(frame).__name__}"
                    ),
                )
            )

        location = self._resolve_location(artifact_id, file_name)
        location.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(frame, "sink_parquet"):
            frame.sink_parquet(str(location))
        elif hasattr(frame, "write_parquet"):
            frame.write_parquet(str(location))
        else:  # pragma: no cover - defensive
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_PERSIST_FAILED",
                    message=(f"Cannot persist frame of type {type(frame).__name__}"),
                )
            )
        size_bytes = location.stat().st_size
        digest = compute_content_hash(location, algorithm="sha256")
        artifact = PersistedArtifact(
            artifact_id=artifact_id,
            kind=kind,
            location=str(location),
            hash=ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest=digest,
            ),
            storage_policy=ArtifactStoragePolicy(
                medium=self._medium,
                retention=self._retention,
            ),
            producer="artifact_store",
            size_bytes=size_bytes,
        )
        _LOGGER.info(
            "Wrote artifact: id=%s kind=%s location=%s size=%s",
            artifact_id,
            kind,
            location,
            size_bytes,
        )
        return artifact

    # -----------------------------------------------------------------
    # Generic write / read
    # -----------------------------------------------------------------
    def write_bytes(
        self,
        *,
        artifact_id: str,
        kind: str,
        file_name: str,
        data: bytes,
    ) -> PersistedArtifact:
        """Write raw bytes and return a typed :class:`PersistedArtifact`."""
        location = self._resolve_location(artifact_id, file_name)
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_bytes(data)
        digest = compute_content_hash(location, algorithm="sha256")
        size_bytes = len(data)
        return PersistedArtifact(
            artifact_id=artifact_id,
            kind=kind,
            location=str(location),
            hash=ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest=digest,
            ),
            storage_policy=ArtifactStoragePolicy(
                medium=self._medium,
                retention=self._retention,
            ),
            producer="artifact_store",
            size_bytes=size_bytes,
        )

    def exists(self, artifact: PersistedArtifact | ArtifactRef) -> bool:
        """Return True if ``artifact`` is present on disk.

        ``PersistedArtifact`` carries ``location``;
        :class:`contracts.common.ArtifactRef` carries ``uri``.
        The function accepts both shapes and consults the
        location-bearing attribute of each.
        """
        if isinstance(artifact, PersistedArtifact):
            path = Path(artifact.location)
        else:
            # ArtifactRef: prefer ``uri``; fall back to
            # ``location`` for backwards compatibility.
            uri = getattr(artifact, "uri", None) or getattr(artifact, "location", None)
            if uri is None:
                return False
            path = Path(uri)
        return path.exists()

    def read_bytes(self, artifact: PersistedArtifact | ArtifactRef) -> bytes:
        """Read ``artifact`` and return its bytes."""
        if isinstance(artifact, PersistedArtifact):
            path = Path(artifact.location)
        else:
            uri = getattr(artifact, "uri", None) or getattr(artifact, "location", None)
            if uri is None:
                raise ArtifactStoreError(
                    _make_issue(
                        code="ARTIFACT_NOT_FOUND",
                        message=(f"ArtifactRef {artifact.artifact_id!r} has no uri"),
                    )
                )
            path = Path(uri)
        if not path.exists():
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_NOT_FOUND",
                    message=f"Artifact not found at {path}",
                )
            )
        return path.read_bytes()

    def read_polars_frame(self, artifact: PersistedArtifact | ArtifactRef) -> "pl.DataFrame":
        """Read ``artifact`` as a Polars DataFrame.

        The function lazy-imports Polars so the store can be
        imported by tests that do not exercise Parquet IO.
        """
        try:
            import polars as pl  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ArtifactStoreError(
                _make_issue(
                    code="POLARS_NOT_INSTALLED",
                    message=(
                        "Polars is required for the Parquet artifact "
                        f"store but is not installed: {exc}"
                    ),
                )
            ) from exc
        if isinstance(artifact, PersistedArtifact):
            path = Path(artifact.location)
        else:
            uri = getattr(artifact, "uri", None) or getattr(artifact, "location", None)
            if uri is None:
                raise ArtifactStoreError(
                    _make_issue(
                        code="ARTIFACT_NOT_FOUND",
                        message=(f"ArtifactRef {artifact.artifact_id!r} has no uri"),
                    )
                )
            path = Path(uri)
        if not path.exists():
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_NOT_FOUND",
                    message=f"Artifact not found at {path}",
                )
            )
        return pl.read_parquet(str(path))

    def delete(self, artifact: PersistedArtifact | ArtifactRef) -> bool:
        """Remove the artifact body.

        Returns True if the file existed and was removed, False
        if the file did not exist (idempotent). The function does
        not consult the artifact's :attr:`ArtifactStoragePolicy`
        for confirmation; deletion is unconditional. Multi-artifact
        directories are not removed.
        """
        if isinstance(artifact, PersistedArtifact):
            path = Path(artifact.location)
        else:
            uri = getattr(artifact, "uri", None) or getattr(artifact, "location", None)
            if uri is None:
                return False
            path = Path(uri)
        if not path.exists():
            return False
        try:
            os.remove(path)
        except OSError as exc:
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_DELETE_FAILED",
                    message=f"Failed to delete {path}: {exc}",
                )
            ) from exc
        return True

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------
    def _resolve_location(self, artifact_id: str, file_name: str) -> Path:
        if not artifact_id or "/" in artifact_id or "\\" in artifact_id:
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_INVALID_ID",
                    message=("artifact_id must be non-empty and must not contain path separators"),
                )
            )
        if not file_name or "/" in file_name or "\\" in file_name:
            raise ArtifactStoreError(
                _make_issue(
                    code="ARTIFACT_INVALID_FILE_NAME",
                    message=("file_name must be non-empty and must not contain path separators"),
                )
            )
        return self._root_dir / artifact_id / file_name
