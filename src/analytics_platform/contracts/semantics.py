"""Semantic column typing contracts (Build Queue v2.1 Task 23).

Public contracts for the ``semantics`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Semantics contracts describe
the *meaning* of a column beyond its physical/logical type: whether a
column is a target, an identifier, a measurement, a timestamp, etc. They
are dependency-light and never embed raw dataframes, file bytes, or
backend objects.

Scope:

- ``SemanticColumnType`` / ``ColumnRole`` — enums of analytics-meaningful
  column kinds and pipeline roles.
- ``SemanticTypeInferenceRequest`` / ``SemanticTypeInferenceReport`` —
  request/result for the semantic-typing stage (4.5).
- ``SemanticColumnProfile`` / ``ColumnRoleAssignment`` — per-column
  semantic typing outputs.
- ``SemanticTypeConfidence`` — bounded confidence score for an inferred
  semantic type.
- ``RiskyColumnUse`` — typed warning raised when a column is used in a
  way that conflicts with its inferred semantic role.

Not implemented here: actual semantic-typing logic. The semantic-typing
stage is deferred to later implementation tasks and must consume these
contracts only.
"""

from __future__ import annotations

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
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import ColumnName, LogicalDataType

__all__ = [
    "SemanticColumnType",
    "ColumnRole",
    "SemanticTypeConfidence",
    "ColumnRoleAssignment",
    "SemanticColumnProfile",
    "SemanticTypeInferenceRequest",
    "SemanticTypeInferenceReport",
    "RiskyColumnUse",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _SemanticsContractModel(BaseModel):
    """Base configuration for semantic contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, file bytes, or
    backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# SemanticColumnType / ColumnRole enums
# ===========================================================================
class SemanticColumnType(str, Enum):
    """Analytics-meaningful semantic types for a column.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. Semantic types describe *what a column
    represents* in the domain (``IDENTIFIER``, ``MEASUREMENT``, ``TIMESTAMP``,
    etc.), independent of physical/logical type. ``UNKNOWN`` is reserved
    for columns whose semantic role could not be inferred.
    """

    IDENTIFIER = "identifier"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    MEASUREMENT = "measurement"
    COUNT = "count"
    TIMESTAMP = "timestamp"
    DATE = "date"
    TEXT = "text"
    BOOLEAN_FLAG = "boolean_flag"
    GEOGRAPHIC = "geographic"
    CURRENCY = "currency"
    RATIO = "ratio"
    UNKNOWN = "unknown"


class ColumnRole(str, Enum):
    """Pipeline role for a column.

    Roles describe *how a column is used in the pipeline* (target,
    feature, exclusion, etc.), independent of its semantic type. A
    column can have at most one role; ``NONE`` means the column has no
    pipeline role assignment.

    Members:

    - ``TARGET`` — the prediction target for a modeling task.
    - ``FEATURE`` — a model input feature.
    - ``EXCLUSION`` — a column the user has explicitly excluded from
      modeling (e.g. PII or leakage-prone).
    - ``GROUP_KEY`` — a column used for grouping / stratification.
    - ``WEIGHT`` — a sample-weight column.
    - ``TIME_INDEX`` — a column used to order / split time-based data.
    - ``NONE`` — no role assignment.
    """

    TARGET = "target"
    FEATURE = "feature"
    EXCLUSION = "exclusion"
    GROUP_KEY = "group_key"
    WEIGHT = "weight"
    TIME_INDEX = "time_index"
    NONE = "none"


# ===========================================================================
# SemanticTypeConfidence / ColumnRoleAssignment
# ===========================================================================
# ``_ConfidenceScore`` is a bounded score in [0.0, 1.0] describing how
# confident the semantic-typing stage is in an inferred type. The bounds
# are enforced at the type-alias level so consumers can rely on the
# range.
_ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]


class SemanticTypeConfidence(_SemanticsContractModel):
    """Bounded confidence score for an inferred semantic type.

    A semantic type confidence is a simple ``(score, algorithm)`` pair
    that downstream consumers (modeling, validation, reporting) can use
    to decide whether the inference is reliable enough to act on. The
    score is bounded to ``[0.0, 1.0]`` (inclusive); ``0.0`` means
    "no confidence" and ``1.0`` means "absolute confidence".

    Fields:

    - ``score``: bounded confidence score in ``[0.0, 1.0]``.
    - ``algorithm``: optional bounded algorithm label (e.g.
      ``"rule_based"``, ``"name_match"``).
    - ``evidence_count``: optional non-negative number of evidence
      signals that contributed to the score.
    - ``notes``: optional bounded human-readable note.
    """

    score: _ConfidenceScore = Field(
        ...,
        description="Bounded confidence score in [0.0, 1.0].",
    )
    algorithm: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded algorithm label (e.g. 'rule_based').",
    )
    evidence_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative number of evidence signals that contributed to the score.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


class ColumnRoleAssignment(_SemanticsContractModel):
    """The pipeline role assigned to a single column.

    A role assignment pairs a :data:`ColumnName` with a :class:`ColumnRole`
    and an optional bounded reason. ``EXCLUSION`` and ``TARGET`` are
    "high-impact" roles whose assignment should be auditable; the
    ``assigned_by`` and ``assigned_at`` fields support that audit trail.

    Fields:

    - ``column_name``: :data:`ColumnName` of the column.
    - ``role``: :class:`ColumnRole` assigned to the column.
    - ``assigned_by``: optional bounded label identifying the actor
      (``"user"``, ``"inference"``, etc.).
    - ``assigned_at_confidence``: optional :class:`SemanticTypeConfidence`
      describing the confidence of the assignment (when the role was
      inferred rather than user-declared).
    - ``reason``: optional bounded human-readable reason.
    - ``metadata``: small bounded string-to-string metadata.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the column.",
    )
    role: ColumnRole = Field(
        ...,
        description="ColumnRole assigned to the column.",
    )
    assigned_by: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded label identifying the actor (e.g. 'user', 'inference').",
    )
    assigned_at_confidence: SemanticTypeConfidence | None = Field(
        default=None,
        description="Optional confidence of the assignment (when role was inferred).",
    )
    reason: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable reason.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# SemanticColumnProfile
# ===========================================================================
class SemanticColumnProfile(_SemanticsContractModel):
    """The semantic-typing result for a single column.

    A semantic column profile pairs a :data:`ColumnName` with the
    inferred :class:`SemanticColumnType`, the optional logical type the
    inference used as evidence, a bounded confidence score, and an
    optional list of alternative semantic types with their own
    confidence scores. It must not embed raw data, sample values, or
    distribution summaries (those belong in the profiling family).

    Fields:

    - ``column_name``: :data:`ColumnName` of the column.
    - ``semantic_type``: inferred :class:`SemanticColumnType`.
    - ``logical_type``: optional :class:`LogicalDataType` that the
      inference used as evidence.
    - ``confidence``: :class:`SemanticTypeConfidence` for the primary
      inference.
    - ``alternatives``: optional tuple of
      ``(SemanticColumnType, SemanticTypeConfidence)`` describing
      alternative inferences (e.g. for tie-breaking).
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the column.",
    )
    semantic_type: SemanticColumnType = Field(
        ...,
        description="Inferred SemanticColumnType.",
    )
    logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional LogicalDataType that the inference used as evidence.",
    )
    confidence: SemanticTypeConfidence = Field(
        ...,
        description="SemanticTypeConfidence for the primary inference.",
    )
    alternatives: tuple[
        tuple[SemanticColumnType, SemanticTypeConfidence], ...
    ] = Field(
        default=(),
        description="Optional tuple of (SemanticColumnType, confidence) alternatives.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _alternative_type_does_not_match_primary(self) -> "SemanticColumnProfile":
        for alt_type, _alt_conf in self.alternatives:
            if alt_type is self.semantic_type:
                raise ValueError(
                    f"SemanticColumnProfile.alternatives must not include the "
                    f"primary semantic_type={self.semantic_type!r}."
                )
        return self


# ===========================================================================
# RiskyColumnUse
# ===========================================================================
class RiskyColumnUse(_SemanticsContractModel):
    """A typed warning raised when a column is used in a risky way.

    A "risky use" is a column whose inferred semantic role conflicts
    with the way the pipeline is using it. For example: a column
    inferred as ``IDENTIFIER`` used as a ``FEATURE``, or a column
    inferred as ``TIMESTAMP`` used as a ``TARGET``. Risky uses do not
    block the pipeline by themselves but are surfaced to reporting and
    the user.

    Fields:

    - ``column_name``: :data:`ColumnName` of the column.
    - ``inferred_semantic_type``: the inferred :class:`SemanticColumnType`.
    - ``inferred_role``: optional inferred :class:`ColumnRole`.
    - ``actual_use``: bounded free-form description of the actual use
      (e.g. ``"used as a regression target"``).
    - ``severity``: :class:`Severity` of the warning (defaults to
      ``WARNING``).
    - ``code``: optional bounded machine-readable code.
    - ``message``: human-readable message.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    column_name: ColumnName = Field(
        ...,
        description="ColumnName of the column.",
    )
    inferred_semantic_type: SemanticColumnType = Field(
        ...,
        description="Inferred SemanticColumnType of the column.",
    )
    inferred_role: ColumnRole | None = Field(
        default=None,
        description="Optional inferred ColumnRole of the column.",
    )
    actual_use: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Bounded free-form description of the actual use (e.g. 'used as a regression target').",
    )
    severity: Severity = Field(
        default=Severity.WARNING,
        description="Severity of the warning. Defaults to WARNING.",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional bounded machine-readable code.",
    )
    message: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional human-readable message.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None


# ===========================================================================
# SemanticTypeInferenceRequest / SemanticTypeInferenceReport
# ===========================================================================
class SemanticTypeInferenceRequest(_SemanticsContractModel):
    """A typed request to infer the semantic type of each column.

    A semantic-typing request takes a :class:`DatasetHandle` plus
    optional user-supplied role overrides and a few configuration knobs.
    It must not reference raw dataframes, file bytes, or backend objects.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the dataset to type.
    - ``role_overrides``: optional tuple of
      :class:`ColumnRoleAssignment` declared by the user. When present,
      these take precedence over inferred roles.
    - ``min_confidence``: optional bounded minimum confidence score
      (``[0.0, 1.0]``). Inferences below this threshold are surfaced as
      :class:`RiskyColumnUse` warnings rather than as accepted
      assignments. Defaults to ``0.5``.
    - ``max_columns``: optional non-negative upper bound on the number
      of columns to inspect.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the dataset to type.",
    )
    role_overrides: tuple[ColumnRoleAssignment, ...] = Field(
        default=(),
        description="Optional tuple of user-declared ColumnRoleAssignment overrides.",
    )
    min_confidence: _ConfidenceScore = Field(
        default=0.5,
        description="Minimum confidence in [0.0, 1.0] to accept an inference.",
    )
    max_columns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of columns.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _role_overrides_column_names_unique(self) -> "SemanticTypeInferenceRequest":
        seen: set[str] = set()
        for override in self.role_overrides:
            if override.column_name in seen:
                raise ValueError(
                    f"SemanticTypeInferenceRequest.role_overrides has duplicate "
                    f"column names: {override.column_name!r}."
                )
            seen.add(override.column_name)
        return self


class SemanticTypeInferenceReport(_SemanticsContractModel):
    """The typed outcome of a semantic-typing request.

    A semantic-typing report carries a per-column
    :class:`SemanticColumnProfile`, the effective :class:`ColumnRole`
    assignments (inferred + user-overridden), the typed risky-use
    warnings, and a few convenience collections. It must not embed raw
    dataframes, sample values, or backend objects.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the typed dataset.
    - ``column_profiles``: tuple of :class:`SemanticColumnProfile`
      (>= 1).
    - ``role_assignments``: tuple of :class:`ColumnRoleAssignment`
      (effective roles, after overrides). May be empty when the user
      did not declare any role and no roles were inferred.
    - ``risky_uses``: tuple of :class:`RiskyColumnUse` (immutable).
    - ``issues`` / ``warnings``: common typed issue/warning collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the typed dataset.",
    )
    column_profiles: tuple[SemanticColumnProfile, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of SemanticColumnProfile (>= 1).",
    )
    role_assignments: tuple[ColumnRoleAssignment, ...] = Field(
        default=(),
        description="Effective ColumnRoleAssignment after overrides.",
    )
    risky_uses: tuple[RiskyColumnUse, ...] = Field(
        default=(),
        description="Tuple of RiskyColumnUse (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during inference (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during inference (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _column_profile_names_unique(self) -> "SemanticTypeInferenceReport":
        seen: set[str] = set()
        for profile in self.column_profiles:
            if profile.column_name in seen:
                raise ValueError(
                    f"SemanticTypeInferenceReport.column_profiles has duplicate "
                    f"column names: {profile.column_name!r}."
                )
            seen.add(profile.column_name)
        return self

    @model_validator(mode="after")
    def _role_assignment_names_unique(self) -> "SemanticTypeInferenceReport":
        seen: set[str] = set()
        for assignment in self.role_assignments:
            if assignment.column_name in seen:
                raise ValueError(
                    f"SemanticTypeInferenceReport.role_assignments has duplicate "
                    f"column names: {assignment.column_name!r}."
                )
            seen.add(assignment.column_name)
        return self
