"""Lineage contracts (Build Queue v2.1 Task 21).

Public contracts for the ``lineage`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Lineage contracts describe the
typed transformation history of a dataset: where data came from, what
operations were applied to it, and the resulting derived datasets. They
are dependency-light (pydantic + stdlib + the shared ``common`` /
``datasets`` / ``execution`` contracts) and never embed raw dataframes
or backend objects.

Scope:

- ``LineageOperationType`` — enum of catalogued transformation kinds.
- ``SourceDatasetRef`` / ``DerivedDatasetRef`` — stable, backend-neutral
  references to upstream sources and downstream derivations.
- ``TransformationRef`` — reference to a specific transformation step
  (does not duplicate the step's request/result contracts).
- ``LineageRecord`` — a single edge in the lineage graph
  (``source -> transformation -> derived``).
- ``LineageGraphSnapshot`` — a typed snapshot of a lineage graph for a
  run, including the records and the run/stage locators that produced
  them.

Not implemented here: actual lineage persistence, graph queries, or
lineage-aware joins. Reporting and pipeline orchestration may read these
contracts but must not import the implementation modules that produce
them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from analytics_platform.contracts.common import (
    DatasetId,
    Issue,
    LineageId,
    RunId,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetRef

__all__ = [
    "LineageOperationType",
    "SourceDatasetRef",
    "DerivedDatasetRef",
    "TransformationRef",
    "LineageRecord",
    "LineageGraphSnapshot",
]


# ---------------------------------------------------------------------------
# Stable identifier / value type aliases
# ---------------------------------------------------------------------------
# ``TransformationId`` is a stable identifier for a specific transformation
# step in a run (e.g. ``"transform-3"`` or a UUID). It is intentionally
# distinct from ``LineageId`` (an identifier for a lineage record/edge) and
# from ``StageId`` (an identifier for a pipeline stage). All three are
# string aliases with the same minimal structural constraints so that
# downstream modules can treat them as plain strings.
_OptionalIdStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]
TransformationId = _OptionalIdStr


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _LineageContractModel(BaseModel):
    """Base configuration for lineage contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, backend objects, or
    file bytes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# LineageOperationType
# ===========================================================================
class LineageOperationType(str, Enum):
    """Catalogued transformation kinds recorded in the lineage graph.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The list is intentionally limited to the kinds
    that downstream consumers (reporting, pipeline, cache invalidation)
    can reason about without inspecting implementation code.

    Members:

    - ``LOAD`` — initial dataset load / ingestion.
    - ``REGISTER`` — dataset registration in the catalog.
    - ``JOIN`` — a (validated) join operation.
    - ``TRANSFORM`` — a generic feature/data transformation.
    - ``PROFILE`` — a profile-only operation that does not produce a new
      dataset (e.g. summary statistics).
    - ``MATERIALIZE`` — materialization of a lazy or backend-managed
      object into a persisted artifact.
    - ``DERIVE`` — a generic catch-all for derived datasets that do not
      fit the above categories.
    - ``DROP`` — a typed drop / exclusion step.
    """

    LOAD = "load"
    REGISTER = "register"
    JOIN = "join"
    TRANSFORM = "transform"
    PROFILE = "profile"
    MATERIALIZE = "materialize"
    DERIVE = "derive"
    DROP = "drop"


# ===========================================================================
# Source / derived / transformation references
# ===========================================================================
class SourceDatasetRef(_LineageContractModel):
    """A reference to a dataset that supplied data into a transformation.

    A source reference is the stable "input side" of a lineage edge. It
    carries a ``DatasetId`` (the unique handle id) plus an optional
    ``DatasetRef`` (the externally-meaningful catalog key) and a snapshot
    fingerprint for content equality checks. It must not contain a raw
    dataframe, file bytes, or backend object.

    Fields:

    - ``dataset_id``: stable ``DatasetId`` of the source dataset.
    - ``dataset_ref``: optional stable ``DatasetRef`` (catalog key).
    - ``fingerprint``: optional bounded content/source fingerprint of
      the snapshot used by this lineage edge.
    - ``role``: optional free-form role label (e.g. ``"left"`` /
      ``"right"`` for joins) for ambiguous multi-source operations.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset_id: DatasetId = Field(
        ...,
        description="Stable DatasetId of the source dataset.",
    )
    dataset_ref: DatasetRef | None = Field(
        default=None,
        description="Optional stable DatasetRef (catalog key).",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content/source fingerprint of the source snapshot.",
    )
    role: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional role label for multi-source operations (e.g. 'left' / 'right').",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class DerivedDatasetRef(_LineageContractModel):
    """A reference to a dataset produced by a transformation.

    A derived reference is the stable "output side" of a lineage edge. It
    mirrors :class:`SourceDatasetRef` and adds an optional lineage-record
    pointer so that downstream consumers can chain records without a
    separate lookup.

    Fields:

    - ``dataset_id``: stable ``DatasetId`` of the derived dataset.
    - ``dataset_ref``: optional stable ``DatasetRef`` (catalog key).
    - ``fingerprint``: optional bounded content/source fingerprint of
      the derived snapshot.
    - ``produced_by_lineage_id``: optional ``LineageId`` of the lineage
      record that produced this derived dataset (self-referential pointer;
      consumers must handle ``None`` and cycles).
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset_id: DatasetId = Field(
        ...,
        description="Stable DatasetId of the derived dataset.",
    )
    dataset_ref: DatasetRef | None = Field(
        default=None,
        description="Optional stable DatasetRef (catalog key).",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content/source fingerprint of the derived snapshot.",
    )
    produced_by_lineage_id: LineageId | None = Field(
        default=None,
        description=(
            "Optional LineageId of the lineage record that produced this derived dataset."
        ),
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class TransformationRef(_LineageContractModel):
    """A reference to a specific transformation step in a run.

    A transformation reference is *not* the transformation's request or
    result — those are owned by the stage-specific contracts (see
    ``docs/contracts/interface-map-v1.1.md``). It is a stable pointer that
    lets lineage edges reference the step that produced them, plus the
    bounded operation kind and a free-form ``code`` for catalogued
    transformations.

    Fields:

    - ``transformation_id``: stable ``TransformationId`` of the step.
    - ``operation``: catalogue :class:`LineageOperationType`.
    - ``code``: optional bounded machine-readable code (e.g.
      ``"join.inner.on=customer_id"``) for catalogued transformations.
    - ``stage_id``: optional :data:`StageId` of the producing stage.
    - ``run_id``: optional :data:`RunId` of the producing run.
    - ``parameters_fingerprint``: optional bounded hash of the
      transformation's parameters for reproducibility checks.
    - ``metadata``: small bounded string-to-string metadata.
    """

    transformation_id: TransformationId = Field(
        ...,
        description="Stable TransformationId of the step.",
    )
    operation: LineageOperationType = Field(
        ...,
        description="Catalogued LineageOperationType of the step.",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded machine-readable code (e.g. 'join.inner.on=customer_id').",
    )
    stage_id: StageId | None = Field(
        default=None,
        description="Optional StageId of the producing stage.",
    )
    run_id: RunId | None = Field(
        default=None,
        description="Optional RunId of the producing run.",
    )
    parameters_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded hash of the transformation's parameters.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# LineageRecord
# ===========================================================================
class LineageRecord(_LineageContractModel):
    """A single edge in the lineage graph: ``sources -> transformation -> derived``.

    A lineage record is the smallest unit of lineage that downstream
    consumers (reporting, cache invalidation, audit) can reason about.
    It is intentionally limited to references and metadata — the actual
    request/result of the transformation lives in the stage-specific
    contracts, not here.

    A record must have at least one source and exactly one derived
    dataset. A ``PROFILE`` operation may legitimately produce zero
    derived datasets (profile-only stages do not materialize a new
    dataset); in that case ``derived`` is ``None`` and ``operation`` is
    :attr:`LineageOperationType.PROFILE`.

    Fields:

    - ``lineage_id``: stable ``LineageId`` of this record.
    - ``operation``: catalogue :class:`LineageOperationType`.
    - ``sources``: tuple of :class:`SourceDatasetRef` (>= 1).
    - ``transformation``: :class:`TransformationRef` describing the step.
    - ``derived``: optional :class:`DerivedDatasetRef` (required unless
      ``operation`` is ``PROFILE``).
    - ``recorded_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``notes``: optional bounded human-readable note.
    - ``issues`` / ``warnings``: typed issue/warning collections.
    - ``metadata``: small bounded string-to-string metadata.
    """

    lineage_id: LineageId = Field(
        ...,
        description="Stable LineageId of this record.",
    )
    operation: LineageOperationType = Field(
        ...,
        description="Catalogued LineageOperationType of the recorded step.",
    )
    sources: tuple[SourceDatasetRef, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of SourceDatasetRef. At least one source is required.",
    )
    transformation: TransformationRef = Field(
        ...,
        description="TransformationRef describing the step.",
    )
    derived: DerivedDatasetRef | None = Field(
        default=None,
        description=(
            "Optional DerivedDatasetRef. Required unless operation is PROFILE."
        ),
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of record creation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Typed issues raised while recording the lineage (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Typed warnings recorded while recording the lineage (immutable).",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _derived_required_unless_profile(self) -> "LineageRecord":
        if self.operation is LineageOperationType.PROFILE:
            return self
        if self.derived is None:
            raise ValueError(
                "LineageRecord requires a DerivedDatasetRef unless operation is PROFILE."
            )
        return self

    @model_validator(mode="after")
    def _sources_deduped_by_dataset_id(self) -> "LineageRecord":
        # Two SourceDatasetRef entries with the same dataset_id + role
        # represent the same source; we reject duplicates at validation
        # time so downstream graph traversal can rely on uniqueness.
        seen: set[tuple[str, str | None]] = set()
        for src in self.sources:
            key = (src.dataset_id, src.role)
            if key in seen:
                raise ValueError(
                    f"LineageRecord has duplicate SourceDatasetRef for "
                    f"dataset_id={src.dataset_id!r} role={src.role!r}."
                )
            seen.add(key)
        return self

    @model_validator(mode="after")
    def _recorded_at_is_timezone_aware(self) -> "LineageRecord":
        if self.recorded_at is not None and self.recorded_at.tzinfo is None:
            object.__setattr__(
                self,
                "recorded_at",
                self.recorded_at.replace(tzinfo=timezone.utc),
            )
        return self


# ===========================================================================
# LineageGraphSnapshot
# ===========================================================================
class LineageGraphSnapshot(_LineageContractModel):
    """A typed snapshot of a lineage graph for a single run.

    A snapshot bundles the set of :class:`LineageRecord` edges produced
    by a run plus the run/stage locators that produced them. It is the
    canonical input to downstream consumers (reporting, audit, cache
    invalidation) and must never embed raw dataframes, file bytes, or
    backend objects.

    Fields:

    - ``snapshot_id``: stable identifier for this snapshot.
    - ``run_id``: :data:`RunId` of the producing run.
    - ``records``: tuple of :class:`LineageRecord` (>= 1).
    - ``captured_at``: optional timezone-aware timestamp of capture.
    - ``root_dataset_ids``: optional tuple of ``DatasetId`` marking the
      root sources in the graph (consumers may derive this from
      ``records``; the field is a convenience for indexing).
    - ``stage_ids``: optional tuple of :data:`StageId` covered by the
      snapshot.
    - ``issues`` / ``warnings``: typed issue/warning collections.
    - ``metadata``: small bounded string-to-string metadata.
    """

    snapshot_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier for this snapshot.",
    )
    run_id: RunId = Field(
        ...,
        description="RunId of the producing run.",
    )
    records: tuple[LineageRecord, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of LineageRecord. At least one record is required.",
    )
    captured_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of snapshot capture.",
    )
    root_dataset_ids: tuple[DatasetId, ...] = Field(
        default=(),
        description="Optional tuple of DatasetId marking the root sources.",
    )
    stage_ids: tuple[StageId, ...] = Field(
        default=(),
        description="Optional tuple of StageId covered by the snapshot.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Typed issues raised while building the snapshot (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Typed warnings recorded while building the snapshot (immutable).",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _lineage_ids_unique_within_snapshot(self) -> "LineageGraphSnapshot":
        seen: set[str] = set()
        for record in self.records:
            if record.lineage_id in seen:
                raise ValueError(
                    f"LineageGraphSnapshot has duplicate LineageRecord with "
                    f"lineage_id={record.lineage_id!r}."
                )
            seen.add(record.lineage_id)
        return self

    @model_validator(mode="after")
    def _captured_at_is_timezone_aware(self) -> "LineageGraphSnapshot":
        if self.captured_at is not None and self.captured_at.tzinfo is None:
            object.__setattr__(
                self,
                "captured_at",
                self.captured_at.replace(tzinfo=timezone.utc),
            )
        return self
