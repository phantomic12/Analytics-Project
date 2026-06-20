"""Common shared contracts for the analytics platform.

These are universal, dependency-light, typed public models used across
pipeline stages and domain modules. They intentionally contain only
standard-library types and Pydantic primitives: no Polars, Pandas, DuckDB,
NumPy, SciPy, or Statsmodels objects are referenced, and no implementation
modules are imported. This keeps the contracts stable, serializable, and
safe for downstream modules to import without pulling heavy compute
dependencies.

Scope (Build Queue v2.1 Task 11):

- Stable ID / value type aliases: ``RunId``, ``DatasetId``, ``ArtifactId``,
  ``StageId``, ``ModelId``, ``ReportId``, ``LineageId``.
- Severity and execution-status enums.
- User-facing issue / warning records.
- Metric value, artifact reference, and stage-result models.

Domain-specific contracts (datasets, schemas, profiling, joins, features,
modeling, validation, reporting, registry, and pipeline orchestration) are
intentionally NOT defined here; they belong to later task-scoped contract
files. This module must not grow domain contracts beyond the minimal
references needed for common shared types.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

__all__ = [
    "RunId",
    "DatasetId",
    "ArtifactId",
    "StageId",
    "ModelId",
    "ReportId",
    "LineageId",
    "Severity",
    "ExecutionStatus",
    "Issue",
    "WarningRecord",
    "MetricValue",
    "ArtifactRef",
    "StageResult",
]


# ---------------------------------------------------------------------------
# Stable ID / value type aliases
# ---------------------------------------------------------------------------
# Lightweight validated string aliases. They impose only minimal, stable
# structural constraints (non-empty, bounded length) so they do not overfit a
# particular ID-generation scheme. They are validated when used as Pydantic
# field types and otherwise behave as plain strings.
_IdStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]

#: Unique identifier for a pipeline run.
RunId = _IdStr
#: Stable identifier for a dataset version/snapshot.
DatasetId = _IdStr
#: Stable identifier for a produced or consumed artifact.
ArtifactId = _IdStr
#: Identifier for a pipeline stage execution.
StageId = _IdStr
#: Identifier for a fitted/registered model.
ModelId = _IdStr
#: Identifier for a generated report.
ReportId = _IdStr
#: Identifier for a lineage record/edge.
LineageId = _IdStr


# ---------------------------------------------------------------------------
# Status / severity enums
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    """Severity level for user-facing issues and warnings.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``INFO`` is the lowest severity and ``CRITICAL``
    is the highest.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExecutionStatus(str, Enum):
    """Lifecycle status of a stage or run execution.

    Values are stable lowercase strings. The terminal states are
    ``SUCCEEDED``, ``FAILED``, ``SKIPPED``, and ``CANCELLED``.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ContractModel(BaseModel):
    """Base configuration for common contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so that the public surface stays explicit and stable
    for downstream consumers. Validation is strict by default.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ---------------------------------------------------------------------------
# User-facing issue / warning records
# ---------------------------------------------------------------------------
class Issue(_ContractModel):
    """A user-facing issue raised during a run.

    Issues carry a stable machine-readable ``code`` (not a free-form message),
    a severity, and a human-readable message. Optional locator fields tie the
    issue to a specific run/stage/dataset. ``context`` is a small, bounded
    piece of typed metadata (string-to-string) and must not carry raw data
    frames or model objects.
    """

    code: str = Field(..., min_length=1, description="Stable machine-readable issue code.")
    severity: Severity = Field(..., description="Severity of the issue.")
    message: str = Field(..., min_length=1, description="Human-readable issue message.")
    run_id: RunId | None = None
    stage_id: StageId | None = None
    dataset_id: DatasetId | None = None
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class WarningRecord(_ContractModel):
    """A non-fatal warning recorded during a run.

    Warnings are advisory: they describe something noteworthy that did not
    stop execution. They share the same locator pattern as :class:`Issue` but
    do not carry a severity (warnings are, by definition, severity
    ``WARNING``).
    """

    code: str = Field(..., min_length=1, description="Stable machine-readable warning code.")
    message: str = Field(..., min_length=1, description="Human-readable warning message.")
    run_id: RunId | None = None
    stage_id: StageId | None = None
    dataset_id: DatasetId | None = None
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ---------------------------------------------------------------------------
# Metrics / artifacts / stage results
# ---------------------------------------------------------------------------
class MetricValue(_ContractModel):
    """A single named scalar metric value.

    The value is a plain ``float`` (ints are coerced) so that metrics remain
    serializable and language-agnostic. ``unit`` is an optional free-form
    string (e.g. ``"seconds"``, ``"rows"``). ``tags`` is small bounded
    string-to-string metadata for grouping/filtering.
    """

    name: str = Field(..., min_length=1, description="Stable metric name.")
    value: float = Field(..., description="Scalar metric value.")
    unit: str | None = Field(default=None, description="Optional unit label.")
    tags: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata for grouping.",
    )


class ArtifactRef(_ContractModel):
    """A stable reference to a produced or consumed artifact.

    An artifact reference is a pointer (``uri``) plus a stable ``kind`` label
    (e.g. ``"dataset"``, ``"report"``, ``"model"``). It deliberately does not
    embed raw data, dataframe handles, or model objects; it only names where
    the artifact lives and how it was produced.
    """

    artifact_id: ArtifactId = Field(..., description="Stable artifact identifier.")
    kind: str = Field(
        ...,
        min_length=1,
        description="Artifact kind, e.g. 'dataset', 'report', 'model'.",
    )
    uri: str = Field(
        ...,
        min_length=1,
        description="Stable location/identifier for the artifact (no raw payload).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class StageResult(_ContractModel):
    """The outcome of executing a single pipeline stage.

    A stage result carries the stage's execution status plus the issues,
    warnings, metrics, and artifact references it produced. Collections are
    modeled as immutable tuples so that the contract itself cannot be mutated
    in place after construction. All nested records are common contracts
    defined in this module.
    """

    stage_id: StageId = Field(..., description="Identifier of the stage that produced this result.")
    status: ExecutionStatus = Field(..., description="Execution status of the stage.")
    run_id: RunId | None = None
    message: str | None = Field(default=None, description="Optional human-readable outcome summary.")
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Issues raised by the stage (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Warnings recorded by the stage (immutable).",
    )
    metrics: tuple[MetricValue, ...] = Field(
        default=(),
        description="Metric values produced by the stage (immutable).",
    )
    artifacts: tuple[ArtifactRef, ...] = Field(
        default=(),
        description="Artifact references produced by the stage (immutable).",
    )