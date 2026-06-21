"""Join contracts (Build Queue v2.1 Task 27).

Public contracts for the ``joins`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Join contracts describe
the typed request/result shapes for stage 4.10 (join validation) and
stage 4.11 (join execution). Per the interface map:

- Joins are optional; they only happen after the profile-only MVP
  checkpoint (Task 108) passes.
- Stage 4.10 (validation) gates stage 4.11 (execution). A blocked
  validation cannot execute without an explicit override.
- ``unsafe`` joins are blocked by default; safe joins pass and
  produce a :class:`JoinedDatasetResult`.
- Reports must record whether a join was used, what its
  approval / risk status was, and any join-induced missingness.

Contracts are dependency-light: they import ``pydantic``, the standard
library, and the shared ``common`` / ``datasets`` / ``schemas`` /
``semantics`` / ``quality`` contracts only. They never embed raw
dataframes, model objects, sample values, or backend objects.

Scope:

- ``JoinType`` / ``JoinCardinality`` / ``JoinRiskLevel`` /
  ``JoinApprovalStatus`` — enums.
- ``ColumnConflictPolicy`` / ``NullKeyPolicy`` /
  ``DuplicateKeyPolicy`` — enums describing how conflicts are
  resolved.
- ``JoinSpec`` / ``JoinKeySpec`` — typed join specification.
- ``JoinValidationRequest`` / ``JoinValidationReport``.
- ``JoinExecutionRequest`` / ``JoinExecutionReport``.
- ``JoinedDatasetResult``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from analytics_platform.contracts.common import (
    DatasetId,
    ExecutionStatus,
    Issue,
    LineageId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle, DatasetRef
from analytics_platform.contracts.schemas import ColumnName

__all__ = [
    "JoinType",
    "JoinCardinality",
    "JoinRiskLevel",
    "JoinApprovalStatus",
    "ColumnConflictPolicy",
    "NullKeyPolicy",
    "DuplicateKeyPolicy",
    "JoinKeySpec",
    "JoinSpec",
    "JoinValidationRequest",
    "JoinValidationReport",
    "JoinExecutionRequest",
    "JoinExecutionReport",
    "JoinedDatasetResult",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _JoinsContractModel(BaseModel):
    """Base configuration for join contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, file bytes, or
    backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# Join enums
# ===========================================================================
class JoinType(str, Enum):
    """Catalogued join types.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``CROSS`` is a documentation-level cross join
    that must be explicitly approved at the validation stage; it is not
    a default for any contract.
    """

    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL_OUTER = "full_outer"
    SEMI_LEFT = "semi_left"
    SEMI_RIGHT = "semi_right"
    ANTI_LEFT = "anti_left"
    ANTI_RIGHT = "anti_right"
    CROSS = "cross"


class JoinCardinality(str, Enum):
    """Observed or expected join cardinality.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``ONE_TO_MANY`` / ``MANY_TO_ONE`` are
    documentation-level; the validation stage reports the *observed*
    cardinality from upstream profiling when available.
    """

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class JoinRiskLevel(str, Enum):
    """Risk level of a join, computed by the validation stage.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``HIGH`` risk joins trigger a default block;
    ``MEDIUM`` risk joins are surfaced as warnings; ``LOW`` risk joins
    are accepted by default.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class JoinApprovalStatus(str, Enum):
    """Approval status of a join after validation.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``APPROVED`` joins may proceed to execution;
    ``BLOCKED`` joins must be explicitly overridden to execute.
    """

    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    BLOCKED = "blocked"


class ColumnConflictPolicy(str, Enum):
    """How column-name conflicts on the join output are resolved.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``RENAME`` is the default for documented
    conflict resolution; ``DROP_RIGHT`` drops the right-side column and
    ``COALESCE`` keeps the left-side column when the right-side is
    missing.
    """

    RENAME = "rename"
    DROP_RIGHT = "drop_right"
    DROP_LEFT = "drop_left"
    COALESCE = "coalesce"
    ERROR = "error"


class NullKeyPolicy(str, Enum):
    """How null keys in the join inputs are treated.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``EXCLUDE`` drops rows whose join key is null
    on either side; ``KEEP`` keeps them in the output; ``ERROR`` treats
    null keys as a validation failure.
    """

    EXCLUDE = "exclude"
    KEEP = "keep"
    ERROR = "error"


class DuplicateKeyPolicy(str, Enum):
    """How duplicate join keys in the join inputs are treated.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``ALLOW`` accepts many-to-many joins as-is;
    ``DEDUPE`` deduplicates on the right side and ``ERROR`` treats
    duplicate keys as a validation failure.
    """

    ALLOW = "allow"
    DEDUPE = "dedupe"
    ERROR = "error"


# ===========================================================================
# JoinKeySpec / JoinSpec
# ===========================================================================
class JoinKeySpec(_JoinsContractModel):
    """A typed specification of a single join key.

    A join key pairs a :data:`ColumnName` on the left side with a
    :data:`ColumnName` on the right side. Multi-key joins use a tuple
    of :class:`JoinKeySpec` entries with the same length.

    Fields:

    - ``left_column``: :data:`ColumnName` of the left-side key column.
    - ``right_column``: :data:`ColumnName` of the right-side key column.
    - ``notes``: optional bounded human-readable note.
    """

    left_column: ColumnName = Field(
        ..., description="ColumnName of the left-side key column."
    )
    right_column: ColumnName = Field(
        ..., description="ColumnName of the right-side key column."
    )
    notes: str | None = Field(
        default=None,
        max_length=512,
        description="Optional bounded human-readable note.",
    )


class JoinSpec(_JoinsContractModel):
    """A typed join specification.

    A join spec is the canonical input to the join-validation stage
    (4.10) and the join-execution stage (4.11). It is intentionally
    limited to references and metadata; it does not carry raw
    dataframes, sample values, or backend objects.

    Fields:

    - ``left_dataset`` / ``right_dataset``: :class:`DatasetHandle` of
      the two sides. ``left_dataset.dataset_id`` and
      ``right_dataset.dataset_id`` must differ.
    - ``join_type``: :class:`JoinType` (defaults to ``INNER``).
    - ``keys``: tuple of :class:`JoinKeySpec` (>= 1).
    - ``left_role`` / ``right_role``: optional bounded role labels
      identifying the join side (``"left"`` / ``"right"`` for
      self-joins; ``"target"`` / ``"feature"`` for feature joins,
      etc.).
    - ``column_conflict_policy`` / ``null_key_policy`` /
      ``duplicate_key_policy``: :class:`ColumnConflictPolicy` /
      :class:`NullKeyPolicy` / :class:`DuplicateKeyPolicy`
      (defaults below).
    - ``expected_cardinality``: optional expected
      :class:`JoinCardinality` (used to flag cardinality drift).
    - ``notes``: optional bounded human-readable note.
    """

    left_dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the left side of the join.",
    )
    right_dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the right side of the join.",
    )
    join_type: JoinType = Field(
        default=JoinType.INNER,
        description="JoinType. Defaults to INNER.",
    )
    keys: tuple[JoinKeySpec, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of JoinKeySpec (>= 1).",
    )
    left_role: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded role label for the left side.",
    )
    right_role: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded role label for the right side.",
    )
    column_conflict_policy: ColumnConflictPolicy = Field(
        default=ColumnConflictPolicy.RENAME,
        description="ColumnConflictPolicy. Defaults to RENAME.",
    )
    null_key_policy: NullKeyPolicy = Field(
        default=NullKeyPolicy.EXCLUDE,
        description="NullKeyPolicy. Defaults to EXCLUDE.",
    )
    duplicate_key_policy: DuplicateKeyPolicy = Field(
        default=DuplicateKeyPolicy.ALLOW,
        description="DuplicateKeyPolicy. Defaults to ALLOW.",
    )
    expected_cardinality: JoinCardinality | None = Field(
        default=None,
        description="Optional expected JoinCardinality used to flag cardinality drift.",
    )
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _datasets_differ(self) -> "JoinSpec":
        if self.left_dataset.dataset_id == self.right_dataset.dataset_id:
            raise ValueError(
                "JoinSpec.left_dataset and right_dataset must refer to "
                "different datasets."
            )
        return self

    @model_validator(mode="after")
    def _keys_unique(self) -> "JoinSpec":
        seen: set[tuple[str, str]] = set()
        for k in self.keys:
            key = (k.left_column, k.right_column)
            if key in seen:
                raise ValueError(
                    f"JoinSpec.keys has duplicate key: {key!r}."
                )
            seen.add(key)
        return self


# ===========================================================================
# JoinValidationRequest / JoinValidationReport
# ===========================================================================
class JoinValidationRequest(_JoinsContractModel):
    """A typed request to validate a join before execution.

    Fields:

    - ``spec``: :class:`JoinSpec` to validate.
    - ``max_join_induced_missingness_ratio``: optional non-negative
      bounded ratio in ``[0.0, 1.0]``. The validation stage reports
      any column whose join-induced missingness exceeds this bound.
    - ``fail_on_high_risk``: when ``True`` (default), ``HIGH`` risk
      joins are auto-blocked. When ``False``, ``HIGH`` risk joins
      are surfaced as warnings.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    spec: JoinSpec = Field(..., description="JoinSpec to validate.")
    max_join_induced_missingness_ratio: Annotated[
        float, Field(ge=0.0, le=1.0)
    ] = Field(
        default=0.1,
        description=(
            "Optional non-negative bounded ratio in [0.0, 1.0] for join-induced "
            "missingness. Defaults to 0.1."
        ),
    )
    fail_on_high_risk: bool = Field(
        default=True,
        description="When True (default), HIGH risk joins are auto-blocked.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class JoinValidationReport(_JoinsContractModel):
    """The typed outcome of validating a :class:`JoinSpec`.

    A join validation report carries the approval status, the risk
    level, the observed cardinality (when computable), the column
    conflict resolution that will be applied at execution, the
    per-column join-induced missingness, the typed warnings, and a
    few convenience summary fields. It must not embed raw data,
    sample values, or backend objects.

    Fields:

    - ``spec``: the :class:`JoinSpec` that was validated.
    - ``approval_status``: :class:`JoinApprovalStatus`.
    - ``risk_level``: :class:`JoinRiskLevel`.
    - ``observed_cardinality``: optional :class:`JoinCardinality`.
    - ``block_reason``: optional bounded human-readable reason
      (populated when ``approval_status == BLOCKED``).
    - ``column_conflict_policy``: :class:`ColumnConflictPolicy` that
      will be applied at execution.
    - ``column_conflicts``: optional tuple of
      ``(ColumnName, ColumnConflictPolicy)`` describing per-column
      conflict resolution. When present, ``column_conflict_policy``
      is the *default* policy; entries override per-column.
    - ``join_induced_missingness``: optional tuple of
      ``(ColumnName, missing_ratio)`` per-column. ``missing_ratio``
      is bounded in ``[0.0, 1.0]``.
    - ``issues`` / ``warnings``: common typed collections.
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    spec: JoinSpec = Field(..., description="JoinSpec that was validated.")
    approval_status: JoinApprovalStatus = Field(
        ..., description="JoinApprovalStatus produced by validation."
    )
    risk_level: JoinRiskLevel = Field(
        ..., description="JoinRiskLevel produced by validation."
    )
    observed_cardinality: JoinCardinality | None = Field(
        default=None,
        description="Optional observed JoinCardinality.",
    )
    block_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable reason. Populated when approval_status == BLOCKED.",
    )
    column_conflict_policy: ColumnConflictPolicy = Field(
        default=ColumnConflictPolicy.RENAME,
        description="ColumnConflictPolicy that will be applied at execution. Defaults to RENAME.",
    )
    column_conflicts: tuple[tuple[ColumnName, ColumnConflictPolicy], ...] = Field(
        default=(),
        description="Optional tuple of (ColumnName, ColumnConflictPolicy) per-column overrides.",
    )
    join_induced_missingness: tuple[tuple[ColumnName, float], ...] = Field(
        default=(),
        description="Optional tuple of (ColumnName, missing_ratio) per-column join-induced missingness.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of report computation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _block_reason_consistent_with_status(self) -> "JoinValidationReport":
        if self.approval_status is JoinApprovalStatus.BLOCKED and not self.block_reason:
            raise ValueError(
                "JoinValidationReport with approval_status=BLOCKED must include "
                "a non-empty block_reason."
            )
        if (
            self.approval_status is not JoinApprovalStatus.BLOCKED
            and self.block_reason
        ):
            raise ValueError(
                "JoinValidationReport with approval_status != BLOCKED must not "
                "include a block_reason."
            )
        return self

    @model_validator(mode="after")
    def _join_induced_missingness_ratios_bounded(self) -> "JoinValidationReport":
        for _col, ratio in self.join_induced_missingness:
            if not (0.0 <= ratio <= 1.0):
                raise ValueError(
                    "JoinValidationReport.join_induced_missingness ratios must "
                    "be in [0.0, 1.0]."
                )
        return self

    @model_validator(mode="after")
    def _column_conflicts_unique(self) -> "JoinValidationReport":
        seen: set[str] = set()
        for col, _policy in self.column_conflicts:
            if col in seen:
                raise ValueError(
                    f"JoinValidationReport.column_conflicts has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "JoinValidationReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self


# ===========================================================================
# JoinExecutionRequest / JoinExecutionReport / JoinedDatasetResult
# ===========================================================================
class JoinExecutionRequest(_JoinsContractModel):
    """A typed request to execute a previously-validated join.

    The execution stage is gated by the validation stage: a
    ``BLOCKED`` validation cannot execute without an explicit
    override. ``JoinExecutionRequest`` records the originating
    validation report so the gating is auditable.

    Fields:

    - ``validation_report``: :class:`JoinValidationReport` that
      approves the join.
    - ``explicit_override``: when ``True``, allows execution even
      when the validation report is ``BLOCKED`` or
      ``CONDITIONALLY_APPROVED``. Defaults to ``False``.
    - ``override_reason``: optional bounded human-readable reason.
      Required when ``explicit_override`` is ``True``.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    validation_report: JoinValidationReport = Field(
        ...,
        description="JoinValidationReport that approves the join.",
    )
    explicit_override: bool = Field(
        default=False,
        description="When True, allows execution even when the validation report is BLOCKED.",
    )
    override_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable reason. Required when explicit_override is True.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _override_consistent_with_status(self) -> "JoinExecutionRequest":
        if self.explicit_override and not self.override_reason:
            raise ValueError(
                "JoinExecutionRequest with explicit_override=True must include "
                "a non-empty override_reason."
            )
        return self

    @model_validator(mode="after")
    def _approved_or_overridden(self) -> "JoinExecutionRequest":
        if self.validation_report.approval_status in (
            JoinApprovalStatus.APPROVED,
            JoinApprovalStatus.CONDITIONALLY_APPROVED,
        ):
            return self
        if self.explicit_override:
            return self
        raise ValueError(
            "JoinExecutionRequest requires an APPROVED or "
            "CONDITIONALLY_APPROVED validation_report, or an explicit "
            "override with a non-empty override_reason."
        )


class JoinExecutionReport(_JoinsContractModel):
    """The typed outcome of executing a join.

    Fields:

    - ``request``: the :class:`JoinExecutionRequest` that produced
      this report.
    - ``result``: the :class:`JoinedDatasetResult` produced by the
      execution stage.
    - ``status``: :class:`ExecutionStatus` of the join execution.
    - ``lineage_id``: optional :data:`LineageId` referencing the
      lineage record produced by the join.
    - ``issues`` / ``warnings``: common typed collections.
    - ``started_at`` / ``finished_at``: optional timezone-aware
      timestamps.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    request: JoinExecutionRequest = Field(
        ...,
        description="JoinExecutionRequest that produced this report.",
    )
    result: "JoinedDatasetResult" = Field(
        ...,
        description="JoinedDatasetResult produced by the join execution.",
    )
    status: ExecutionStatus = Field(
        ...,
        description="ExecutionStatus of the join execution.",
    )
    lineage_id: LineageId | None = Field(
        default=None,
        description="Optional LineageId referencing the lineage record produced by the join.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during execution (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during execution (immutable).",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of execution start.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of execution finish.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _timestamps_timezone_aware(self) -> "JoinExecutionReport":
        for field_name in ("started_at", "finished_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(
                    self, field_name, value.replace(tzinfo=timezone.utc)
                )
        return self


class JoinedDatasetResult(_JoinsContractModel):
    """The typed result of a successful join.

    A joined dataset result is the bridge between the join execution
    stage and downstream consumers (catalog, schema, profiling,
    features, reporting). It must not embed raw dataframes, sample
    values, or backend objects.

    Fields:

    - ``result_dataset``: :class:`DatasetHandle` registered as the
      joined output.
    - ``left_dataset_id`` / ``right_dataset_id``: ``DatasetId`` of
      the two sides.
    - ``result_dataset_ref``: optional stable :class:`DatasetRef`.
    - ``left_row_count`` / ``right_row_count``: optional
      non-negative row counts of the input sides.
    - ``result_row_count``: optional non-negative row count of the
      join output.
    - ``left_key_columns`` / ``right_key_columns``: tuple of
      :data:`ColumnName` for the join keys actually used.
    - ``observed_cardinality``: optional :class:`JoinCardinality`
      observed during execution.
    - ``column_conflicts_applied``: optional tuple of
      ``(ColumnName, ColumnConflictPolicy)`` describing per-column
      resolution that was actually applied.
    - ``lineage_id``: optional :data:`LineageId` referencing the
      lineage record produced by the join.
    - ``produced_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    result_dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle registered as the joined output.",
    )
    left_dataset_id: DatasetId = Field(
        ..., description="DatasetId of the left side."
    )
    right_dataset_id: DatasetId = Field(
        ..., description="DatasetId of the right side."
    )
    result_dataset_ref: DatasetRef | None = Field(
        default=None,
        description="Optional stable DatasetRef (catalog key).",
    )
    left_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count of the left side.",
    )
    right_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count of the right side.",
    )
    result_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count of the join output.",
    )
    left_key_columns: tuple[ColumnName, ...] = Field(
        default=(),
        description="Tuple of ColumnName for the left-side join keys actually used.",
    )
    right_key_columns: tuple[ColumnName, ...] = Field(
        default=(),
        description="Tuple of ColumnName for the right-side join keys actually used.",
    )
    observed_cardinality: JoinCardinality | None = Field(
        default=None,
        description="Optional observed JoinCardinality.",
    )
    column_conflicts_applied: tuple[tuple[ColumnName, ColumnConflictPolicy], ...] = Field(
        default=(),
        description="Optional tuple of (ColumnName, ColumnConflictPolicy) per-column resolution actually applied.",
    )
    lineage_id: LineageId | None = Field(
        default=None,
        description="Optional LineageId referencing the lineage record produced by the join.",
    )
    produced_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of result production.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _left_right_differ(self) -> "JoinedDatasetResult":
        if self.left_dataset_id == self.right_dataset_id:
            raise ValueError(
                "JoinedDatasetResult.left_dataset_id and right_dataset_id must differ."
            )
        return self

    @model_validator(mode="after")
    def _key_columns_lengths_match(self) -> "JoinedDatasetResult":
        if len(self.left_key_columns) != len(self.right_key_columns):
            raise ValueError(
                "JoinedDatasetResult.left_key_columns and right_key_columns "
                "must have the same length."
            )
        return self

    @model_validator(mode="after")
    def _column_conflicts_unique(self) -> "JoinedDatasetResult":
        seen: set[str] = set()
        for col, _policy in self.column_conflicts_applied:
            if col in seen:
                raise ValueError(
                    f"JoinedDatasetResult.column_conflicts_applied has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self

    @model_validator(mode="after")
    def _produced_at_is_timezone_aware(self) -> "JoinedDatasetResult":
        if self.produced_at is not None and self.produced_at.tzinfo is None:
            object.__setattr__(
                self,
                "produced_at",
                self.produced_at.replace(tzinfo=timezone.utc),
            )
        return self


# Resolve forward references inside ``JoinExecutionReport``.
JoinExecutionReport.model_rebuild()
