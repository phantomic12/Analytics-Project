"""Artifact persistence contracts (Build Queue v2.1 Task 15).

Public, dependency-light contracts that describe *durable references* to
persisted artifacts and the *storage policy* governing them. They intentionally
contain only standard-library types and Pydantic primitives plus the shared
common ID/value types from Task 11. No Polars, Pandas, DuckDB, NumPy, SciPy,
Statsmodels, or any implementation module is imported, and no raw dataframes,
tables, model objects, backend handles, or large inline payloads are stored.

Scope (Build Queue v2.1 Task 15):

- ``ArtifactHash``: typed, serializable content-hash representation.
- ``ArtifactStoragePolicy``: policy describing how an artifact is stored,
  retained, and referenced.
- ``PersistedArtifact``: durable artifact metadata (location, kind, hash,
  producer/stage metadata, storage policy, optional bounded metadata).
- ``DatasetArtifactRef``: dataset-specific artifact reference for persisted
  dataset outputs such as Parquet artifacts.

Not implemented here:

- Cache invalidation contracts (Task 16).
- Visual/table/chart artifact contracts (Task 17).
- Artifact store runtime behavior (IO/catalog/reporting/registry runtime).
- Dataset, lineage, schema, modeling, validation, reporting, registry, and
  pipeline orchestration contracts.

Downstream consumers (IO, catalog, reporting, registry, cache) may import these
references without pulling runtime or heavy compute dependencies.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.common import (
    ArtifactId,
    DatasetId,
    RunId,
    StageId,
)

__all__ = [
    "ArtifactHashAlgorithm",
    "ArtifactHash",
    "ArtifactStorageMedium",
    "ArtifactRetention",
    "ArtifactStoragePolicy",
    "PersistedArtifact",
    "DatasetArtifactRef",
]  # noqa: E501 (ArtifactRef re-exported from common.py)


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ArtifactContractModel(BaseModel):
    """Base configuration for artifact persistence contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so that the public surface stays explicit and stable
    for downstream consumers. There is deliberately no field for raw
    dataframes, tables, model objects, backend runtime handles, callables,
    sessions, connections, or large inline payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# ArtifactHash
# ===========================================================================
class ArtifactHashAlgorithm(str, Enum):
    """Stable content-hash algorithm labels used by :class:`ArtifactHash`.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. Only well-known, broadly available algorithm
    labels are listed. ``IDENTITY`` is reserved for size-only / fingerprint
    references where no cryptographic hash is available; it must still carry a
    non-empty ``digest`` and should not be used where integrity verification is
    required.

    Members:

    - ``SHA256``: SHA-256 hex digest.
    - ``SHA1``: SHA-1 hex digest (legacy compatibility only).
    - ``BLAKE3``: BLAKE3 hex digest.
    - ``XXHASH``: xxHash hex digest (non-cryptographic fingerprint).
    - ``IDENTITY``: size/fingerprint only, no cryptographic hash.
    """

    SHA256 = "sha256"
    SHA1 = "sha1"
    BLAKE3 = "blake3"
    XXHASH = "xxhash"
    IDENTITY = "identity"


class ArtifactHash(_ArtifactContractModel):
    """Typed, serializable content-hash representation for an artifact.

    Carries *only* the algorithm label and the hex/string digest plus an
    optional digest-size hint. It deliberately does not embed the raw artifact
    bytes, a dataframe, a file handle, or any large inline payload. Downstream
    consumers use this to verify integrity or compare artifacts without
    loading the artifact body.

    Fields:

    - ``algorithm``: stable content-hash algorithm label.
    - ``digest``: non-empty hex/string digest of the artifact content.
    - ``digest_size_bytes``: optional non-negative size of the digest in bytes
      (informational only; not the artifact size).
    """

    algorithm: ArtifactHashAlgorithm = Field(
        ...,
        description="Stable content-hash algorithm label.",
    )
    digest: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Non-empty hex/string digest of the artifact content.",
    )
    digest_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative digest size in bytes (informational only).",
    )


# ===========================================================================
# ArtifactStoragePolicy
# ===========================================================================
class ArtifactStorageMedium(str, Enum):
    """Where/how a persisted artifact is stored.

    Values are stable lowercase strings. These are storage *medium labels*
    only; they do not implement IO, catalog, or backend behavior.

    - ``LOCAL_FS``: local filesystem path.
    - ``OBJECT_STORE``: object store (e.g. S3/GCS/Azure Blob) referenced by URI.
    - ``REGISTRY``: artifact managed/recorded by the run registry.
    """

    LOCAL_FS = "local_fs"
    OBJECT_STORE = "object_store"
    REGISTRY = "registry"


class ArtifactRetention(str, Enum):
    """Retention class for a persisted artifact.

    Values are stable lowercase strings. Retention is a *policy label* only;
    it does not implement deletion or lifecycle enforcement.

    - ``EPHEMERAL``: short-lived, may be reclaimed at any time (e.g. scratch).
    - ``RUN_SCOPED``: retained for the lifetime of the producing run.
    - ``PERSISTENT``: durable across runs (default for persisted artifacts).
    """

    EPHEMERAL = "ephemeral"
    RUN_SCOPED = "run_scoped"
    PERSISTENT = "persistent"


class ArtifactStoragePolicy(_ArtifactContractModel):
    """Policy describing how an artifact is stored, retained, and referenced.

    Declares storage intent only. It does not implement IO, catalog,
    reporting, registry, cache, or backend runtime behavior. Durable artifacts
    default to immutable (``mutable=False``) and persistent retention.

    Fields:

    - ``medium``: storage medium label.
    - ``retention``: retention class; ``PERSISTENT`` by default.
    - ``mutable``: whether the artifact body may be mutated; ``False`` by
      default (durable artifacts are immutable).
    - ``replication``: optional replication factor (``>= 1``).
    - ``compression``: optional short stable compression label (e.g. ``"zstd"``).
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    medium: ArtifactStorageMedium = Field(
        ...,
        description="Storage medium label for the artifact.",
    )
    retention: ArtifactRetention = Field(
        default=ArtifactRetention.PERSISTENT,
        description="Retention class; PERSISTENT by default for durable artifacts.",
    )
    mutable: bool = Field(
        default=False,
        description="Whether the artifact body may be mutated; False by default.",
    )
    replication: int | None = Field(
        default=None,
        ge=1,
        description="Optional replication factor (>= 1).",
    )
    compression: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional short stable compression label (e.g. 'zstd').",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# PersistedArtifact
# ===========================================================================
class PersistedArtifact(_ArtifactContractModel):
    """Durable metadata describing a persisted artifact.

    References an artifact by a stable location/URI and a stable ``kind``
    label, plus its content hash, producer/stage metadata, and storage policy.
    Must not embed raw data, dataframes, tables, model objects, backend runtime
    handles, callables, sessions, connections, or large inline payloads.

    Fields:

    - ``artifact_id``: stable artifact identifier.
    - ``kind``: stable artifact type/kind label (e.g. ``"dataset"``,
      ``"report"``, ``"model"``).
    - ``location``: stable path or URI-like location of the artifact body.
    - ``hash``: typed content-hash representation.
    - ``storage_policy``: storage/retention policy for the artifact.
    - ``producer``: optional short stable producer label (e.g. stage name).
    - ``producer_run_id`` / ``producer_stage_id``: optional provenance locators.
    - ``created_at``: optional ISO-8601 creation timestamp.
    - ``size_bytes``: optional non-negative best-effort body size in bytes.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    artifact_id: ArtifactId = Field(..., description="Stable artifact identifier.")
    kind: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable artifact type/kind label (e.g. 'dataset', 'report', 'model').",
    )
    location: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Stable path or URI-like location of the artifact body (no raw payload).",
    )
    hash: ArtifactHash = Field(..., description="Typed content-hash representation.")
    storage_policy: ArtifactStoragePolicy = Field(
        ...,
        description="Storage/retention policy for the artifact.",
    )
    producer: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short stable producer label (e.g. stage name).",
    )
    producer_run_id: RunId | None = Field(
        default=None,
        description="Optional run that produced the artifact.",
    )
    producer_stage_id: StageId | None = Field(
        default=None,
        description="Optional stage that produced the artifact.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 creation timestamp.",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort body size in bytes.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# DatasetArtifactRef
# ===========================================================================
class DatasetArtifactRef(_ArtifactContractModel):
    """Dataset-specific artifact reference for persisted dataset outputs.

    A durable reference to a persisted dataset artifact (e.g. a Parquet file
    written by IO). Includes path/location, type/kind, content hash, producer
    metadata, and storage policy, plus dataset-specific descriptors
    (``dataset_id``, ``format``, optional row/column counts, and an optional
    schema fingerprint). Must not embed raw dataframes, tables, arrays, model
    objects, backend runtime handles, callables, sessions, connections, or
    large inline payloads.

    Fields:

    - ``dataset_id``: stable identifier of the persisted dataset.
    - ``artifact_id``: stable artifact identifier.
    - ``kind``: stable artifact type/kind label; defaults to ``"dataset"``.
    - ``format``: stable dataset artifact format label (e.g. ``"parquet"``).
    - ``location``: stable path or URI-like location of the dataset artifact.
    - ``hash``: typed content-hash representation.
    - ``storage_policy``: storage/retention policy for the artifact.
    - ``producer``: optional short stable producer label (e.g. stage name).
    - ``producer_run_id`` / ``producer_stage_id``: optional provenance locators.
    - ``rows`` / ``columns``: optional non-negative best-effort descriptors.
    - ``schema_fingerprint``: optional stable fingerprint of the dataset schema.
    - ``created_at``: optional ISO-8601 creation timestamp.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    dataset_id: DatasetId = Field(..., description="Stable identifier of the persisted dataset.")
    artifact_id: ArtifactId = Field(..., description="Stable artifact identifier.")
    kind: str = Field(
        default="dataset",
        min_length=1,
        max_length=128,
        description="Stable artifact type/kind label; defaults to 'dataset'.",
    )
    format: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable dataset artifact format label (e.g. 'parquet', 'csv').",
    )
    location: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Stable path or URI-like location of the dataset artifact (no raw payload).",
    )
    hash: ArtifactHash = Field(..., description="Typed content-hash representation.")
    storage_policy: ArtifactStoragePolicy = Field(
        ...,
        description="Storage/retention policy for the dataset artifact.",
    )
    producer: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short stable producer label (e.g. stage name).",
    )
    producer_run_id: RunId | None = Field(
        default=None,
        description="Optional run that produced the dataset artifact.",
    )
    producer_stage_id: StageId | None = Field(
        default=None,
        description="Optional stage that produced the dataset artifact.",
    )
    rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort row count descriptor.",
    )
    columns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort column count descriptor.",
    )
    schema_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional stable fingerprint of the dataset schema.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 creation timestamp.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )
