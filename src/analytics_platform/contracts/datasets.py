"""Dataset identity, load, ingestion, and fingerprint contracts (Tasks 18-20).

Public contracts for the ``datasets`` contract family listed in
``docs/contracts/contracts-index-v1.1.md``. This module is dependency-light:
it imports only ``pydantic``, the standard library, and the shared
``analytics_platform.contracts.common`` types. It must never import
``polars``, ``pandas``, ``duckdb``, ``numpy``, ``scipy``, ``statsmodels``,
``matplotlib``, or any implementation module, and it must never store raw
dataframes, model objects, or backend handles in public fields.

Scope:

- Task 18: ``DatasetFormat``, ``DatasetRole``, ``StorageBackend``,
  ``DatasetMaterializationStatus``, ``DatasetHandle``, ``DatasetRef``.
- Task 19: ``DatasetLoadRequest``, ``DatasetLoadResult``, ``IngestionReport``,
  ``RegisteredDatasetResult``.
- Task 20: ``DatasetFingerprint``, ``SourceFileMetadata``.

``RegisteredDatasetResult`` is owned by this family because it is the typed
output of the dataset registration stage that consumes the load/ingestion
contracts above; it shares the same dependency-light, no-raw-object
discipline as the rest of the module.

Not implemented here: actual IO, backend selection, schema inference,
profiling, joins, feature matrices, modeling, reporting, registry, or
pipeline orchestration. This module defines *typed shapes only*.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from analytics_platform.contracts.common import (
    ArtifactId,
    DatasetId,
    ExecutionStatus,
    Issue,
    LineageId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)

__all__ = [
    # Task 18 — identity and handle
    "DatasetFormat",
    "DatasetRole",
    "StorageBackend",
    "DatasetMaterializationStatus",
    "DatasetHandle",
    "DatasetRef",
    # Task 19 — load and ingestion
    "DatasetLoadRequest",
    "DatasetLoadResult",
    "IngestionReport",
    "RegisteredDatasetResult",
    # Task 20 — fingerprint
    "DatasetFingerprint",
    "SourceFileMetadata",
]


# ---------------------------------------------------------------------------
# Stable identifier / value type aliases
# ---------------------------------------------------------------------------
# Lightweight validated string aliases. They impose only minimal, stable
# structural constraints (non-empty, bounded length) so they do not overfit a
# particular ID-generation scheme.
_IdStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]

#: Stable identifier for a dataset version/snapshot registered in the catalog.
DatasetRef = _IdStr


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _DatasetsContractModel(BaseModel):
    """Base configuration for dataset contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so that the public surface stays explicit and stable
    for downstream consumers. There is deliberately no field for raw
    dataframes, file bytes, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# Task 18 — Dataset identity and handle contracts
# ===========================================================================
class DatasetFormat(str, Enum):
    """Supported/planned dataset formats for IO and ingestion.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``UNKNOWN`` is reserved for files that cannot be
    classified into a known format; consumers must treat it as a typed
    ingestion issue, not as a silent pass-through.
    """

    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
    JSONL = "jsonl"
    TSV = "tsv"
    UNKNOWN = "unknown"


class DatasetRole(str, Enum):
    """Logical role of a dataset in the pipeline.

    Roles are pipeline-level annotations, not file-format properties. They
    describe how a dataset is used (source, joined, derived, target, etc.) so
    downstream stages and reporting can reason about provenance without
    inspecting raw data.
    """

    SOURCE = "source"
    DERIVED = "derived"
    JOINED = "joined"
    FEATURE_MATRIX = "feature_matrix"
    TARGET = "target"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


class StorageBackend(str, Enum):
    """Storage backend category for a dataset's source location.

    Only documented backend categories are listed here. This enum does not
    implement storage behavior; it labels where a dataset lives so the IO
    layer can route a load request correctly.
    """

    LOCAL_FS = "local_fs"
    IN_MEMORY = "in_memory"
    HTTP = "http"
    S3 = "s3"


class DatasetMaterializationStatus(str, Enum):
    """Lifecycle status of a dataset handle's underlying object.

    Materialization status is independent from execution status: a dataset
    can be ``REGISTERED`` but not yet ``MATERIALIZED``, or it can be
    ``MATERIALIZED`` while a downstream stage is still ``RUNNING``.
    """

    REGISTERED = "registered"
    LAZY = "lazy"
    MATERIALIZED = "materialized"
    STALE = "stale"
    FAILED = "failed"


class DatasetHandle(_DatasetsContractModel):
    """A serializable, backend-neutral handle to a registered dataset.

    A dataset handle carries only metadata and stable identifiers. It must
    not contain the actual dataframe, file bytes, a Polars/Pandas/DuckDB
    object, a callable, a backend session, or any raw backend handle.
    Downstream stages resolve the handle through the catalog/IO layer, never
    through this contract.

    Fields:

    - ``dataset_id``: stable identifier for the dataset version/snapshot.
    - ``dataset_ref``: stable, externally-meaningful reference (catalog key).
    - ``name``: short human-readable dataset name.
    - ``role``: logical role of the dataset in the pipeline.
    - ``format``: detected/planned dataset format.
    - ``storage_backend``: storage backend category that owns the source.
    - ``materialization_status``: current materialization status of the
      underlying object (separate from execution status).
    - ``fingerprint``: optional content/source fingerprint. See
      :class:`DatasetFingerprint` (Task 20).
    - ``source_uri``: optional bounded string/uri of the source location.
    - ``schema_fingerprint``: optional stable fingerprint/hash of the
      observed schema (cheap equality check without materializing).
    - ``row_count_estimate``: optional non-negative estimated row count.
    - ``registered_at``: optional timezone-aware timestamp of registration.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    dataset_id: DatasetId = Field(..., description="Stable dataset identifier.")
    dataset_ref: DatasetRef = Field(
        ...,
        description="Stable, externally-meaningful catalog reference for the dataset.",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Short human-readable dataset name.",
    )
    role: DatasetRole = Field(
        default=DatasetRole.SOURCE,
        description="Logical role of the dataset in the pipeline.",
    )
    format: DatasetFormat = Field(
        default=DatasetFormat.UNKNOWN,
        description="Detected or planned dataset format.",
    )
    storage_backend: StorageBackend = Field(
        default=StorageBackend.LOCAL_FS,
        description="Storage backend category that owns the source location.",
    )
    materialization_status: DatasetMaterializationStatus = Field(
        default=DatasetMaterializationStatus.REGISTERED,
        description="Current materialization status of the underlying object.",
    )
    fingerprint: DatasetFingerprint | None = Field(
        default=None,
        description="Optional content/source fingerprint for the dataset. See Task 20.",
    )
    source_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded uri/path of the source location.",
    )
    schema_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional stable fingerprint/hash of the observed schema.",
    )
    row_count_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative estimated row count. Estimate only.",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registration.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _registered_at_is_timezone_aware(self) -> DatasetHandle:
        if self.registered_at is not None and self.registered_at.tzinfo is None:
            # Convert naive datetimes to UTC instead of rejecting them. This
            # keeps common JSON-deserialization paths ergonomic while still
            # guaranteeing that stored values are timezone-aware.
            object.__setattr__(
                self,
                "registered_at",
                self.registered_at.replace(tzinfo=UTC),
            )
        return self


# ===========================================================================
# Task 20 — Dataset fingerprint contracts
# ===========================================================================
class SourceFileMetadata(_DatasetsContractModel):
    """Stable, typed metadata about a dataset's source file.

    Source-file metadata describes the on-disk artifact that a dataset was
    loaded from: a bounded path/uri, an optional size and content hash, and
    a few optional provenance fields. It must not contain the file bytes or
    any backend-managed object.

    Fields:

    - ``uri``: bounded path/uri identifying the source file.
    - ``size_bytes``: optional non-negative file size in bytes.
    - ``content_hash``: optional bounded content hash (e.g. SHA-256 hex).
    - ``last_modified_at``: optional timezone-aware last-modified timestamp.
    - ``encoding``: optional bounded encoding label (e.g. ``"utf-8"``).
    - ``compression``: optional bounded compression label (e.g. ``"snappy"``).
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    uri: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Bounded path/uri identifying the source file.",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative file size in bytes.",
    )
    content_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content hash (e.g. SHA-256 hex).",
    )
    last_modified_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware last-modified timestamp.",
    )
    encoding: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded encoding label (e.g. 'utf-8').",
    )
    compression: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded compression label (e.g. 'snappy').",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _last_modified_at_is_timezone_aware(self) -> SourceFileMetadata:
        if self.last_modified_at is not None and self.last_modified_at.tzinfo is None:
            object.__setattr__(
                self,
                "last_modified_at",
                self.last_modified_at.replace(tzinfo=UTC),
            )
        return self


class DatasetFingerprint(_DatasetsContractModel):
    """A stable, backend-neutral fingerprint for a dataset.

    A fingerprint combines a content hash with optional structural metadata
    so that two datasets can be compared without materializing their data.
    It must never contain raw bytes, dataframe samples, or backend objects.

    A fingerprint may be constructed in two modes:

    - Content-only: ``content_hash`` is required and ``source`` is omitted.
      Two datasets with the same ``content_hash`` are considered
      content-equal regardless of where they were loaded from.
    - Source-attached: ``source`` is provided in addition to the content
      hash, so the same content loaded from a different location still
      carries provenance.

    Fields:

    - ``algorithm``: bounded hash algorithm label (e.g. ``"sha256"``).
    - ``content_hash``: bounded hex digest produced by ``algorithm``.
    - ``source``: optional :class:`SourceFileMetadata` describing where the
      fingerprinted bytes came from.
    - ``computed_at``: optional timezone-aware timestamp of computation.
    - ``row_count``: optional non-negative row count snapshot at compute time.
    - ``schema_fingerprint``: optional stable fingerprint/hash of the schema.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    algorithm: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Hash algorithm label (e.g. 'sha256').",
    )
    content_hash: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Bounded hex digest produced by the algorithm.",
    )
    source: SourceFileMetadata | None = Field(
        default=None,
        description="Optional source-file metadata describing the fingerprinted bytes.",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of fingerprint computation.",
    )
    row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count snapshot at compute time.",
    )
    schema_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional stable fingerprint/hash of the observed schema.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> DatasetFingerprint:
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=UTC),
            )
        return self


# Resolve the forward reference inside ``DatasetHandle.fingerprint``. Doing
# this at module import time keeps the public type-hint resolvable for static
# analyzers without reordering the class definitions above.
DatasetHandle.model_rebuild()


# ===========================================================================
# Task 19 — Dataset load and ingestion contracts
# ===========================================================================
class DatasetLoadRequest(_DatasetsContractModel):
    """A typed request to load a dataset into the pipeline.

    A load request names the source location (path/uri), the expected
    format, and the optional fingerprint/schema hints used for cheap
    mismatch detection. It must not carry raw bytes, dataframe samples, or
    backend objects.

    Fields:

    - ``source_uri``: bounded path/uri identifying the dataset location.
    - ``format``: expected/detected dataset format.
    - ``storage_backend``: storage backend category that owns the source.
    - ``expected_fingerprint``: optional pre-declared
      :class:`DatasetFingerprint` for early mismatch detection.
    - ``expected_schema_fingerprint``: optional pre-declared schema hash.
    - ``name``: optional short human-readable dataset name. Defaults to
      derived from ``source_uri`` when omitted.
    - ``role``: logical role the loaded dataset should assume on
      registration. Defaults to :attr:`DatasetRole.SOURCE`.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    source_uri: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Bounded path/uri identifying the dataset location.",
    )
    format: DatasetFormat = Field(
        default=DatasetFormat.UNKNOWN,
        description="Expected or detected dataset format.",
    )
    storage_backend: StorageBackend = Field(
        default=StorageBackend.LOCAL_FS,
        description="Storage backend category that owns the source location.",
    )
    expected_fingerprint: DatasetFingerprint | None = Field(
        default=None,
        description="Optional pre-declared fingerprint for early mismatch detection.",
    )
    expected_schema_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional pre-declared schema fingerprint for early mismatch detection.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short human-readable dataset name.",
    )
    role: DatasetRole = Field(
        default=DatasetRole.SOURCE,
        description="Logical role the loaded dataset should assume on registration.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class DatasetLoadResult(_DatasetsContractModel):
    """The typed outcome of loading a dataset.

    A load result references a successful load via a
    :class:`DatasetHandle` plus an :class:`IngestionReport`. It must never
    embed a raw dataframe, file bytes, or backend object. Failures are
    represented as ``status == ExecutionStatus.FAILED`` with at least one
    ``Issue`` of severity :attr:`Severity.ERROR` or higher on ``ingestion``.

    Fields:

    - ``request``: the originating :class:`DatasetLoadRequest`.
    - ``status``: execution status of the load stage.
    - ``handle``: optional :class:`DatasetHandle` produced on success.
    - ``ingestion``: :class:`IngestionReport` summarizing the load attempt.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    request: DatasetLoadRequest = Field(
        ...,
        description="The originating DatasetLoadRequest.",
    )
    status: ExecutionStatus = Field(
        ...,
        description="Execution status of the load stage.",
    )
    handle: DatasetHandle | None = Field(
        default=None,
        description="Optional dataset handle produced on success.",
    )
    ingestion: IngestionReport = Field(
        ...,
        description="Ingestion report summarizing the load attempt.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _handle_consistent_with_status(self) -> DatasetLoadResult:
        status = self.status
        # ``is None`` is checked because ExecutionStatus is a str-Enum, so a
        # truthy check would also match ``SUCCEEDED.value``.
        succeeded = status is ExecutionStatus.SUCCEEDED
        if succeeded and self.handle is None:
            raise ValueError(
                "DatasetLoadResult with status=SUCCEEDED must include a DatasetHandle."
            )
        if not succeeded and self.handle is not None:
            raise ValueError(
                "DatasetLoadResult with non-SUCCEEDED status must not include a DatasetHandle."
            )
        return self


class IngestionReport(_DatasetsContractModel):
    """A typed summary of a dataset load attempt.

    An ingestion report carries a small, bounded snapshot of what happened
    during the load: row counts, format detection outcome, optional
    fingerprint/source metadata, and the issues/warnings raised. It must
    never embed raw dataframes, file bytes, or backend objects.

    Fields:

    - ``detected_format``: format detected by the IO layer (may differ from
      the requested format). ``UNKNOWN`` means the format could not be
      classified.
    - ``requested_format``: format requested by the caller (if any).
    - ``rows_read``: optional non-negative number of rows read.
    - ``bytes_read``: optional non-negative number of bytes consumed.
    - ``fingerprint``: optional :class:`DatasetFingerprint` computed during
      ingestion.
    - ``source``: optional :class:`SourceFileMetadata` for the source file.
    - ``started_at`` / ``finished_at``: optional timezone-aware timestamps.
    - ``issues`` / ``warnings``: typed issue/warning collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    detected_format: DatasetFormat = Field(
        default=DatasetFormat.UNKNOWN,
        description="Format detected by the IO layer. UNKNOWN means unclassified.",
    )
    requested_format: DatasetFormat | None = Field(
        default=None,
        description="Format requested by the caller, if any.",
    )
    rows_read: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative number of rows read.",
    )
    bytes_read: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative number of bytes consumed.",
    )
    fingerprint: DatasetFingerprint | None = Field(
        default=None,
        description="Optional fingerprint computed during ingestion.",
    )
    source: SourceFileMetadata | None = Field(
        default=None,
        description="Optional source-file metadata for the source file.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of load start.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of load finish.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Typed issues raised during ingestion (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Typed warnings recorded during ingestion (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _timestamps_are_timezone_aware(self) -> IngestionReport:
        for field_name in ("started_at", "finished_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(self, field_name, value.replace(tzinfo=UTC))
        return self

    @model_validator(mode="after")
    def _has_error_issue_when_format_unknown(self) -> IngestionReport:
        # An UNKNOWN detected format must be accompanied by at least one
        # ERROR-or-higher Issue so downstream stages cannot silently treat
        # an unclassified file as a successful load.
        if self.detected_format is DatasetFormat.UNKNOWN:
            has_error = any(
                issue.severity in (Severity.ERROR, Severity.CRITICAL) for issue in self.issues
            )
            if not has_error:
                raise ValueError(
                    "IngestionReport with detected_format=UNKNOWN must include at "
                    "least one ERROR-or-higher Issue."
                )
        return self


class RegisteredDatasetResult(_DatasetsContractModel):
    """The typed outcome of registering a dataset in the catalog.

    A registration result is the bridge between the IO layer (which produces
    a :class:`DatasetLoadResult`) and the catalog (which assigns the
    dataset a stable handle and lineage record). It must never embed a raw
    dataframe, file bytes, or backend object.

    Fields:

    - ``handle``: the :class:`DatasetHandle` registered in the catalog.
    - ``status``: execution status of the registration stage.
    - ``ingestion``: the :class:`IngestionReport` from the load attempt.
    - ``lineage_id``: optional :data:`LineageId` referencing the catalog
      lineage record produced by registration.
    - ``artifact_id``: optional :data:`ArtifactId` referencing a persisted
      artifact produced by registration (see Task 15 ``ArtifactRef``).
    - ``issues`` / ``warnings``: typed issue/warning collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    handle: DatasetHandle = Field(
        ...,
        description="Dataset handle registered in the catalog.",
    )
    status: ExecutionStatus = Field(
        ...,
        description="Execution status of the registration stage.",
    )
    ingestion: IngestionReport = Field(
        ...,
        description="Ingestion report from the originating load attempt.",
    )
    lineage_id: LineageId | None = Field(
        default=None,
        description="Optional lineage identifier referencing the catalog lineage record.",
    )
    artifact_id: ArtifactId | None = Field(
        default=None,
        description="Optional artifact identifier referencing a persisted artifact.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Typed issues raised during registration (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Typed warnings recorded during registration (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _succeeded_status_requires_no_error_issues(self) -> RegisteredDatasetResult:
        if self.status is not ExecutionStatus.SUCCEEDED:
            return self
        for issue in self.issues:
            if issue.severity in (Severity.ERROR, Severity.CRITICAL):
                raise ValueError(
                    "RegisteredDatasetResult with status=SUCCEEDED must not include "
                    "ERROR-or-higher Issues."
                )
        return self


# Resolve the forward references inside ``DatasetLoadResult.ingestion`` and
# ``IngestionReport.fingerprint``/``source`` after the types are defined.
DatasetLoadResult.model_rebuild()
IngestionReport.model_rebuild()
