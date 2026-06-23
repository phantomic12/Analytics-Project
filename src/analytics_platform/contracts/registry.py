"""Registry contracts (Build Queue v2.1 Task 41).

Public contracts for the ``registry`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Registry contracts describe
the typed result / model / dataset / artifact registry entries and
the bounded read / write request/result shapes. They are
dependency-light: they import ``pydantic``, the standard library,
and the shared ``common`` / ``datasets`` / ``modeling`` contracts
only. They never embed raw dataframes, sample values, model
objects, or backend objects.

Per the architecture-test plan (section 3.5), registry writing is
owned by pipeline; domain modules do not write directly. The
contracts here are the typed entry / request / result shapes that
the pipeline uses; the actual file-based registry implementation
(Task 102) is deferred to a later implementation task.

Scope:

- ``RunRegistryRecord`` (Task 41).
- ``ResultRegistryEntry`` / ``ModelRegistryEntry`` /
  ``DatasetRegistryEntry`` / ``ArtifactRegistryEntry``.
- ``RegistryWriteRequest`` / ``RegistryWriteResult``.
- ``RunHistoryQuery``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from analytics_platform.contracts.common import (
    ArtifactId,
    DatasetId,
    Issue,
    ModelId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.modeling import ModelResult, ModelSpec

__all__ = [
    "RunStatus",
    "RunRegistryRecord",
    "ResultRegistryEntry",
    "ModelRegistryEntry",
    "DatasetRegistryEntry",
    "ArtifactRegistryEntry",
    "RegistryWriteRequest",
    "RegistryWriteResult",
    "RunHistoryQuery",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _RegistryContractModel(BaseModel):
    """Base configuration for registry contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``). They never embed raw dataframes, sample
    values, model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for confidence / progress.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Enums
# ===========================================================================
class RunStatus(str, Enum):
    """Catalogued run statuses for the run registry.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ===========================================================================
# RunRegistryRecord
# ===========================================================================
class RunRegistryRecord(_RegistryContractModel):
    """A typed registry record for a single run (Task 32 / 41).

    A run registry record is the canonical entry that the pipeline
    writes to the file-based registry at the end of stage 4.32
    (run manifest writing) and stage 4.33 (file-based registry
    writing). The implementation of the file-based registry
    (Task 102) is deferred; this contract is the typed shape
    that the implementation will read and write.

    Fields:

    - ``run_id``: :data:`RunId` of the run.
    - ``status``: :class:`RunStatus`.
    - ``started_at`` / ``finished_at``: optional timezone-aware
      timestamps.
    - ``stage_ids``: tuple of :data:`StageId` covered by the run.
    - ``config_hash``: optional bounded hash of the resolved
      configuration.
    - ``dataset_ids``: tuple of :data:`DatasetId` consumed by
      the run.
    - ``model_ids``: tuple of :data:`ModelId` produced by the
      run.
    - ``artifact_ids``: tuple of :data:`ArtifactId` produced by
      the run.
    - ``lineage_snapshot_id``: optional stable id of the
      lineage snapshot.
    - ``progress``: optional bounded ratio in ``[0.0, 1.0]``
      (``0.0`` = not started, ``1.0`` = complete).
    - ``issues`` / ``warnings``: common typed collections.
    - ``registered_at``: optional timezone-aware timestamp.
    - ``metadata``: small bounded string-to-string metadata.
    """

    run_id: RunId = Field(..., description="RunId of the run.")
    status: RunStatus = Field(..., description="RunStatus.")
    started_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run start.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run finish.",
    )
    stage_ids: tuple[StageId, ...] = Field(
        default=(),
        description="Tuple of StageId covered by the run.",
    )
    config_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded hash of the resolved configuration.",
    )
    dataset_ids: tuple[DatasetId, ...] = Field(
        default=(),
        description="Tuple of DatasetId consumed by the run.",
    )
    model_ids: tuple[ModelId, ...] = Field(
        default=(),
        description="Tuple of ModelId produced by the run.",
    )
    artifact_ids: tuple[ArtifactId, ...] = Field(
        default=(),
        description="Tuple of ArtifactId produced by the run.",
    )
    lineage_snapshot_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional stable id of the lineage snapshot.",
    )
    progress: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded progress ratio in [0.0, 1.0].",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during the run (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during the run (immutable).",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registry entry creation.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _stage_ids_unique(self) -> "RunRegistryRecord":
        seen: set[str] = set()
        for stage_id in self.stage_ids:
            if stage_id in seen:
                raise ValueError(f"RunRegistryRecord has duplicate stage_id: {stage_id!r}.")
            seen.add(stage_id)
        return self

    @model_validator(mode="after")
    def _timestamps_timezone_aware(self) -> "RunRegistryRecord":
        for field_name in ("started_at", "finished_at", "registered_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(self, field_name, value.replace(tzinfo=timezone.utc))
        return self

    @model_validator(mode="after")
    def _finished_after_started(self) -> "RunRegistryRecord":
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("RunRegistryRecord.finished_at must be >= started_at.")
        return self


# ===========================================================================
# Result / Model / Dataset / Artifact registry entries
# ===========================================================================
class ResultRegistryEntry(_RegistryContractModel):
    """A typed result-registry entry.

    Fields:

    - ``entry_id``: stable identifier.
    - ``run_id``: :data:`RunId` of the run that produced the
      result.
    - ``result_kind``: bounded result-kind label
      (``"coefficient_table"`` / ``"dataset_profile"`` / etc.).
    - ``result_id``: bounded result identifier within the
      registry.
    - ``registered_at``: optional timezone-aware timestamp.
    - ``fingerprint``: optional bounded content fingerprint.
    - ``metadata``: small bounded string-to-string metadata.
    """

    entry_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    run_id: RunId = Field(
        ...,
        description="RunId of the run that produced the result.",
    )
    result_kind: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Bounded result-kind label.",
    )
    result_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Bounded result identifier within the registry.",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registry entry creation.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _registered_at_is_timezone_aware(self) -> "ResultRegistryEntry":
        if self.registered_at is not None and self.registered_at.tzinfo is None:
            object.__setattr__(
                self,
                "registered_at",
                self.registered_at.replace(tzinfo=timezone.utc),
            )
        return self


class ModelRegistryEntry(_RegistryContractModel):
    """A typed model-registry entry.

    Fields:

    - ``entry_id``: stable identifier.
    - ``model_id``: :data:`ModelId` of the registered model.
    - ``run_id``: :data:`RunId` of the run that produced the
      model.
    - ``model_spec``: the :class:`ModelSpec` of the registered
      model.
    - ``model_result``: optional :class:`ModelResult`.
    - ``registered_at``: optional timezone-aware timestamp.
    - ``fingerprint``: optional bounded content fingerprint.
    - ``metadata``: small bounded string-to-string metadata.
    """

    entry_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    model_id: ModelId = Field(..., description="ModelId of the registered model.")
    run_id: RunId = Field(
        ...,
        description="RunId of the run that produced the model.",
    )
    model_spec: ModelSpec = Field(..., description="ModelSpec of the registered model.")
    model_result: ModelResult | None = Field(
        default=None,
        description="Optional ModelResult.",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registry entry creation.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _model_ids_match(self) -> "ModelRegistryEntry":
        if self.model_result is not None and self.model_result.model_id != self.model_id:
            raise ValueError(
                "ModelRegistryEntry.model_result.model_id must equal ModelRegistryEntry.model_id."
            )
        return self

    @model_validator(mode="after")
    def _registered_at_is_timezone_aware(self) -> "ModelRegistryEntry":
        if self.registered_at is not None and self.registered_at.tzinfo is None:
            object.__setattr__(
                self,
                "registered_at",
                self.registered_at.replace(tzinfo=timezone.utc),
            )
        return self


class DatasetRegistryEntry(_RegistryContractModel):
    """A typed dataset-registry entry.

    Fields:

    - ``entry_id``: stable identifier.
    - ``dataset_id``: :data:`DatasetId` of the registered
      dataset.
    - ``dataset_handle``: :class:`DatasetHandle` of the
      registered dataset.
    - ``run_id``: :data:`RunId` of the run that produced the
      entry.
    - ``registered_at``: optional timezone-aware timestamp.
    - ``fingerprint``: optional bounded content fingerprint.
    - ``metadata``: small bounded string-to-string metadata.
    """

    entry_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    dataset_id: DatasetId = Field(..., description="DatasetId of the registered dataset.")
    dataset_handle: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the registered dataset.",
    )
    run_id: RunId = Field(
        ...,
        description="RunId of the run that produced the entry.",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registry entry creation.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _dataset_ids_match(self) -> "DatasetRegistryEntry":
        if self.dataset_handle.dataset_id != self.dataset_id:
            raise ValueError(
                "DatasetRegistryEntry.dataset_handle.dataset_id must equal "
                "DatasetRegistryEntry.dataset_id."
            )
        return self

    @model_validator(mode="after")
    def _registered_at_is_timezone_aware(self) -> "DatasetRegistryEntry":
        if self.registered_at is not None and self.registered_at.tzinfo is None:
            object.__setattr__(
                self,
                "registered_at",
                self.registered_at.replace(tzinfo=timezone.utc),
            )
        return self


class ArtifactRegistryEntry(_RegistryContractModel):
    """A typed artifact-registry entry.

    Fields:

    - ``entry_id``: stable identifier.
    - ``artifact_id``: :data:`ArtifactId` of the registered
      artifact.
    - ``artifact_kind``: bounded artifact-kind label
      (``"dataset"`` / ``"model"`` / ``"report"`` / etc.).
    - ``run_id``: :data:`RunId` of the run that produced the
      artifact.
    - ``uri``: bounded uri/path of the artifact.
    - ``fingerprint``: optional bounded content fingerprint.
    - ``registered_at``: optional timezone-aware timestamp.
    - ``metadata``: small bounded string-to-string metadata.
    """

    entry_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    artifact_id: ArtifactId = Field(
        ...,
        description="ArtifactId of the registered artifact.",
    )
    artifact_kind: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Bounded artifact-kind label.",
    )
    run_id: RunId = Field(
        ...,
        description="RunId of the run that produced the artifact.",
    )
    uri: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Bounded uri/path of the artifact.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint.",
    )
    registered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of registry entry creation.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _registered_at_is_timezone_aware(self) -> "ArtifactRegistryEntry":
        if self.registered_at is not None and self.registered_at.tzinfo is None:
            object.__setattr__(
                self,
                "registered_at",
                self.registered_at.replace(tzinfo=timezone.utc),
            )
        return self


# ===========================================================================
# Registry write request / result
# ===========================================================================
class RegistryWriteRequest(_RegistryContractModel):
    """A typed request to write to the file-based registry.

    Per the architecture-test plan (section 3.5), registry writing
    is owned by pipeline; the request shape is the typed
    contract that pipeline uses.

    Fields:

    - ``run_record``: :class:`RunRegistryRecord` to write (the
      canonical entry produced at stage 4.33).
    - ``result_entries``: optional tuple of
      :class:`ResultRegistryEntry`.
    - ``model_entries``: optional tuple of
      :class:`ModelRegistryEntry`.
    - ``dataset_entries``: optional tuple of
      :class:`DatasetRegistryEntry`.
    - ``artifact_entries``: optional tuple of
      :class:`ArtifactRegistryEntry`.
    - ``overwrite``: when ``True``, existing entries with the
      same id are overwritten. Defaults to ``False``.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    run_record: RunRegistryRecord = Field(..., description="RunRegistryRecord to write.")
    result_entries: tuple[ResultRegistryEntry, ...] = Field(
        default=(),
        description="Optional tuple of ResultRegistryEntry.",
    )
    model_entries: tuple[ModelRegistryEntry, ...] = Field(
        default=(),
        description="Optional tuple of ModelRegistryEntry.",
    )
    dataset_entries: tuple[DatasetRegistryEntry, ...] = Field(
        default=(),
        description="Optional tuple of DatasetRegistryEntry.",
    )
    artifact_entries: tuple[ArtifactRegistryEntry, ...] = Field(
        default=(),
        description="Optional tuple of ArtifactRegistryEntry.",
    )
    overwrite: bool = Field(
        default=False,
        description="When True, existing entries with the same id are overwritten.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _entry_ids_unique(self) -> "RegistryWriteRequest":
        for field_name in (
            "result_entries",
            "model_entries",
            "dataset_entries",
            "artifact_entries",
        ):
            seen: set[str] = set()
            for entry in getattr(self, field_name):
                if entry.entry_id in seen:
                    raise ValueError(
                        f"RegistryWriteRequest.{field_name} has duplicate "
                        f"entry_id: {entry.entry_id!r}."
                    )
                seen.add(entry.entry_id)
        return self


class RegistryWriteResult(_RegistryContractModel):
    """The typed outcome of a registry write (stage 4.32 output).

    Fields:

    - ``run_id``: :data:`RunId` of the run that was written.
    - ``wrote_run_record``: whether the run record was written.
    - ``result_entry_count``: optional non-negative count of
      result entries written.
    - ``model_entry_count``: optional non-negative count of
      model entries written.
    - ``dataset_entry_count``: optional non-negative count of
      dataset entries written.
    - ``artifact_entry_count``: optional non-negative count of
      artifact entries written.
    - ``issues`` / ``warnings``: common typed collections.
    - ``written_at``: optional timezone-aware timestamp.
    """

    run_id: RunId = Field(..., description="RunId of the run that was written.")
    wrote_run_record: bool = Field(..., description="Whether the run record was written.")
    result_entry_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of result entries written.",
    )
    model_entry_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of model entries written.",
    )
    dataset_entry_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of dataset entries written.",
    )
    artifact_entry_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of artifact entries written.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during writing (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during writing (immutable).",
    )
    written_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of writing.",
    )

    @model_validator(mode="after")
    def _written_at_is_timezone_aware(self) -> "RegistryWriteResult":
        if self.written_at is not None and self.written_at.tzinfo is None:
            object.__setattr__(
                self,
                "written_at",
                self.written_at.replace(tzinfo=timezone.utc),
            )
        return self


# ===========================================================================
# RunHistoryQuery
# ===========================================================================
class RunHistoryQuery(_RegistryContractModel):
    """A typed query for run history (Task 41).

    Fields:

    - ``limit``: optional non-negative upper bound on the number
      of records returned. ``None`` means "no bound".
    - ``since`` / ``until``: optional timezone-aware timestamps
      (inclusive range).
    - ``status_filter``: optional :class:`RunStatus` filter.
    - ``run_id_prefix``: optional bounded prefix filter.
    - ``notes``: optional bounded human-readable note.
    """

    limit: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of records returned.",
    )
    since: datetime | None = Field(
        default=None,
        description="Optional timezone-aware inclusive lower bound on started_at.",
    )
    until: datetime | None = Field(
        default=None,
        description="Optional timezone-aware inclusive upper bound on started_at.",
    )
    status_filter: RunStatus | None = Field(
        default=None,
        description="Optional RunStatus filter.",
    )
    run_id_prefix: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded prefix filter on run_id.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _since_le_until(self) -> "RunHistoryQuery":
        if self.since is not None and self.until is not None and self.until < self.since:
            raise ValueError("RunHistoryQuery.until must be >= since.")
        return self

    @model_validator(mode="after")
    def _timestamps_timezone_aware(self) -> "RunHistoryQuery":
        for field_name in ("since", "until"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(self, field_name, value.replace(tzinfo=timezone.utc))
        return self
