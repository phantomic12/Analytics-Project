"""Schema contracts (Build Queue v2.1 Task 22).

Public contracts for the ``schemas`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Schema contracts describe the
typed shape of a dataset's columns: physical types (what the storage
layer reports), logical types (what analytics code reasons about), and
the request/result shapes for schema inference and validation. They are
dependency-light and never embed raw dataframes, file bytes, or backend
objects.

Scope:

- ``LogicalDataType`` / ``PhysicalDataType`` — enums of abstract and
  concrete types.
- ``ColumnSchema`` — physical + logical type for a single column.
- ``ObservedSchema`` — observed columns for a dataset (inference output).
- ``ExpectedColumnSchema`` / ``ExpectedSchema`` — user-declared expected
  schema (validation input).
- ``SchemaInferenceRequest`` — request to infer a schema.
- ``SchemaValidationRequest`` — request to validate an observed schema
  against an expected schema.
- ``SchemaValidationReport`` — typed outcome of validation.
- ``SchemaIssue`` — typed per-column issue raised by inference or
  validation.

Not implemented here: actual schema inference, semantic typing, or
schema validation logic. Those are deferred to later implementation
tasks and must consume these contracts only.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle

__all__ = [
    "LogicalDataType",
    "PhysicalDataType",
    "ColumnSchema",
    "ObservedSchema",
    "ExpectedColumnSchema",
    "ExpectedSchema",
    "SchemaInferenceRequest",
    "SchemaValidationRequest",
    "SchemaValidationReport",
    "SchemaIssue",
]


# ---------------------------------------------------------------------------
# Stable identifier / value type aliases
# ---------------------------------------------------------------------------
# ``ColumnName`` is a stable, bounded identifier for a column. Columns are
# addressed by name throughout the platform; using a separate alias here
# (rather than a plain ``str``) lets the contracts index and downstream
# modules reference column identity without ad-hoc strings.
ColumnName = Annotated[str, StringConstraints(min_length=1, max_length=256)]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _SchemasContractModel(BaseModel):
    """Base configuration for schema contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, file bytes, or
    backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# Data type enums
# ===========================================================================
class LogicalDataType(str, Enum):
    """Abstract, analytics-meaningful data types.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. Logical types are what the rest of the platform
    reasons about (``INTEGER`` vs ``FLOAT`` vs ``STRING`` etc.) and are
    independent of any backend's physical type vocabulary.
    """

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CATEGORICAL = "categorical"
    DATE = "date"
    DATETIME = "datetime"
    TIMEDELTA = "timedelta"
    BINARY = "binary"
    UNKNOWN = "unknown"


class PhysicalDataType(str, Enum):
    """Concrete physical data types reported by the storage layer.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. Physical types are the backend's vocabulary
    (e.g. ``int32``, ``float64``, ``utf8``). They are independent of
    analytics-meaningful :class:`LogicalDataType` and may map to multiple
    logical types (``int8`` and ``int64`` both map to ``INTEGER``).
    """

    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    BOOL = "bool"
    UTF8 = "utf8"
    LARGE_UTF8 = "large_utf8"
    DATE32 = "date32"
    DATE64 = "date64"
    TIMESTAMP = "timestamp"
    BINARY = "binary"
    LIST = "list"
    STRUCT = "struct"
    NULL = "null"
    UNKNOWN = "unknown"


# ===========================================================================
# ColumnSchema / ObservedSchema / ExpectedSchema
# ===========================================================================
class ColumnSchema(_SchemasContractModel):
    """The physical and logical type of a single column.

    A column schema is the smallest unit of schema information. It pairs
    a stable :data:`ColumnName` with a :class:`PhysicalDataType` (what
    the storage layer reported) and an optional :class:`LogicalDataType`
    (what analytics code reasons about; inferred separately by the
    semantic-typing stage). It must not contain raw column data or
    sample values.

    Fields:

    - ``name``: stable column name.
    - ``physical_type``: physical type reported by the storage layer.
    - ``logical_type``: optional analytics-meaningful type.
    - ``nullable``: optional nullable flag (``True``/``False``/``None``
      when unknown).
    - ``ordinal``: optional non-negative column index in the parent
      schema. ``None`` when the schema is not ordered (e.g. dict-like).
    - ``description``: optional bounded human-readable description.
    - ``metadata``: small bounded string-to-string metadata.
    """

    name: ColumnName = Field(..., description="Stable column name.")
    physical_type: PhysicalDataType = Field(
        ...,
        description="Physical type reported by the storage layer.",
    )
    logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional analytics-meaningful logical type.",
    )
    nullable: bool | None = Field(
        default=None,
        description="Optional nullable flag. None when unknown.",
    )
    ordinal: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative column index. None when unordered.",
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable description.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class ObservedSchema(_SchemasContractModel):
    """The observed columns for a dataset (output of schema inference).

    An observed schema is the typed output of stage 4.4
    (:class:`SchemaInferenceRequest` -> :class:`ObservedSchema`). It
    carries the columns in deterministic insertion order and a
    fingerprint for cheap equality checks. It must not contain raw
    column data or sample values.

    Fields:

    - ``columns``: tuple of :class:`ColumnSchema`. May be empty for a
      dataset with no columns (e.g. an empty Parquet file).
    - ``fingerprint``: optional bounded content fingerprint of the
      observed schema (e.g. SHA-256 hex of a canonical encoding).
    - ``row_count_estimate``: optional non-negative row count estimate
      observed during inference.
    - ``notes``: optional bounded human-readable note.
    - ``metadata``: small bounded string-to-string metadata.
    """

    columns: tuple[ColumnSchema, ...] = Field(
        default=(),
        description="Tuple of ColumnSchema in deterministic insertion order.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint of the observed schema.",
    )
    row_count_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count estimate observed during inference.",
    )
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _column_names_unique(self) -> "ObservedSchema":
        seen: set[str] = set()
        for col in self.columns:
            if col.name in seen:
                raise ValueError(
                    f"ObservedSchema has duplicate ColumnSchema for column name={col.name!r}."
                )
            seen.add(col.name)
        return self


class ExpectedColumnSchema(_SchemasContractModel):
    """A user-declared expected schema for a single column.

    An expected column schema pairs a :data:`ColumnName` with an optional
    :class:`PhysicalDataType` and/or :class:`LogicalDataType`. The
    validation stage compares an :class:`ObservedSchema` against an
    :class:`ExpectedSchema` to produce a
    :class:`SchemaValidationReport`.

    At least one of ``physical_type`` or ``logical_type`` must be
    provided; otherwise the validator has nothing to check.

    Fields:

    - ``name``: stable column name.
    - ``physical_type``: optional expected physical type.
    - ``logical_type``: optional expected logical type.
    - ``nullable``: optional expected nullable flag (``True``/``False``/
      ``None`` when "do not care").
    - ``required``: whether the column is required to be present. Defaults
      to ``True``.
    - ``description``: optional bounded human-readable description.
    - ``metadata``: small bounded string-to-string metadata.
    """

    name: ColumnName = Field(..., description="Stable column name.")
    physical_type: PhysicalDataType | None = Field(
        default=None,
        description="Optional expected physical type.",
    )
    logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional expected logical type.",
    )
    nullable: bool | None = Field(
        default=None,
        description="Optional expected nullable flag. None means 'do not care'.",
    )
    required: bool = Field(
        default=True,
        description="Whether the column is required to be present in the observed schema.",
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable description.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _at_least_one_type(self) -> "ExpectedColumnSchema":
        if self.physical_type is None and self.logical_type is None:
            raise ValueError(
                "ExpectedColumnSchema requires at least one of physical_type or logical_type."
            )
        return self


class ExpectedSchema(_SchemasContractModel):
    """A user-declared expected schema (validation input).

    An expected schema is the typed input to stage 4.6
    (:class:`SchemaValidationRequest` -> :class:`SchemaValidationReport`).
    It declares the columns the user expects to find in the observed
    schema plus, optionally, the schema-level expectations (fingerprint
    equality, row-count bounds).

    Fields:

    - ``columns``: tuple of :class:`ExpectedColumnSchema`. May be empty
      (e.g. "I expect the dataset to have no columns").
    - ``expected_fingerprint``: optional bounded fingerprint the
      observed schema must match exactly.
    - ``min_row_count`` / ``max_row_count``: optional non-negative
      row-count bounds. ``max_row_count`` must be ``>= min_row_count``
      when both are set.
    - ``strict_extra_columns``: when ``True`` (default), columns
      present in the observed schema but not declared here are reported
      as :attr:`SchemaIssue` issues. When ``False``, extra columns are
      allowed (recorded as info-level metadata).
    - ``description``: optional bounded human-readable description.
    - ``metadata``: small bounded string-to-string metadata.
    """

    columns: tuple[ExpectedColumnSchema, ...] = Field(
        default=(),
        description="Tuple of ExpectedColumnSchema.",
    )
    expected_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded fingerprint the observed schema must match exactly.",
    )
    min_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative minimum row count.",
    )
    max_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative maximum row count.",
    )
    strict_extra_columns: bool = Field(
        default=True,
        description=(
            "When True, columns present in the observed schema but not "
            "declared here are reported as SchemaIssue issues."
        ),
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable description.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _column_names_unique(self) -> "ExpectedSchema":
        seen: set[str] = set()
        for col in self.columns:
            if col.name in seen:
                raise ValueError(
                    f"ExpectedSchema has duplicate ExpectedColumnSchema for "
                    f"column name={col.name!r}."
                )
            seen.add(col.name)
        return self

    @model_validator(mode="after")
    def _row_count_bounds_consistent(self) -> "ExpectedSchema":
        if (
            self.min_row_count is not None
            and self.max_row_count is not None
            and self.max_row_count < self.min_row_count
        ):
            raise ValueError("ExpectedSchema max_row_count must be >= min_row_count.")
        return self


# ===========================================================================
# SchemaIssue
# ===========================================================================
class SchemaIssue(_SchemasContractModel):
    """A typed issue raised during schema inference or validation.

    A schema issue is a structured :class:`Issue` that includes the
    column the issue refers to (when applicable). It is intentionally
    limited to references and metadata so it can be safely embedded in
    :class:`SchemaValidationReport` without leaking raw data.

    Fields:

    - ``code``: stable machine-readable code (e.g.
      ``"SCHEMA_MISSING_REQUIRED_COLUMN"``).
    - ``severity``: :class:`Severity` of the issue.
    - ``message``: human-readable message.
    - ``column_name``: optional :data:`ColumnName` the issue refers to.
    - ``expected_physical_type`` / ``expected_logical_type``: optional
      expected types for the issue column.
    - ``observed_physical_type`` / ``observed_logical_type``: optional
      observed types for the issue column.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``context``: small bounded string-to-string metadata.
    """

    code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable issue code.",
    )
    severity: Severity = Field(..., description="Severity of the issue.")
    message: str = Field(..., min_length=1, description="Human-readable issue message.")
    column_name: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName the issue refers to.",
    )
    expected_physical_type: PhysicalDataType | None = Field(
        default=None,
        description="Optional expected physical type for the issue column.",
    )
    expected_logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional expected logical type for the issue column.",
    )
    observed_physical_type: PhysicalDataType | None = Field(
        default=None,
        description="Optional observed physical type for the issue column.",
    )
    observed_logical_type: LogicalDataType | None = Field(
        default=None,
        description="Optional observed logical type for the issue column.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# SchemaInferenceRequest
# ===========================================================================
class SchemaInferenceRequest(_SchemasContractModel):
    """A typed request to infer the schema of a dataset.

    A schema inference request takes a :class:`DatasetHandle` (the
    dataset to introspect) and a few optional hints. It must not
    reference raw dataframes, file bytes, or backend objects.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the dataset to introspect.
    - ``expected_fingerprint_hint``: optional bounded fingerprint
      hint; if the dataset's known fingerprint matches, inference may
      short-circuit.
    - ``max_columns``: optional non-negative upper bound on the number
      of columns to inspect. ``None`` means "no bound".
    - ``sample_row_count``: optional non-negative row count to sample
      during inference. ``None`` means "infer from the full dataset".
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the dataset to introspect.",
    )
    expected_fingerprint_hint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded fingerprint hint for short-circuiting inference.",
    )
    max_columns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of columns.",
    )
    sample_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count to sample during inference.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# SchemaValidationRequest / SchemaValidationReport
# ===========================================================================
class SchemaValidationRequest(_SchemasContractModel):
    """A typed request to validate an observed schema against an expected one.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the dataset being validated.
    - ``observed``: :class:`ObservedSchema` produced by the inference
      stage.
    - ``expected``: :class:`ExpectedSchema` produced by the user /
      config.
    - ``fail_on_warning``: when ``True``, a single WARNING-level issue
      causes the report's status to be FAIL. Defaults to ``False``
      (warnings are advisory).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the dataset being validated.",
    )
    observed: ObservedSchema = Field(
        ...,
        description="ObservedSchema produced by the inference stage.",
    )
    expected: ExpectedSchema = Field(
        ...,
        description="ExpectedSchema produced by the user / config.",
    )
    fail_on_warning: bool = Field(
        default=False,
        description="When True, a single WARNING-level issue causes FAIL status.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class SchemaValidationReport(_SchemasContractModel):
    """The typed outcome of a schema validation request.

    A schema validation report carries the result (``pass``/``fail``),
    a list of typed :class:`SchemaIssue` entries, optional common
    :class:`Issue` / :class:`WarningRecord` collections, and a few
    convenience summary fields. It must not embed raw dataframes,
    sample values, or backend objects.

    A report is considered ``pass`` when the ``passed`` field is
    ``True``. ``passed`` is computed from the presence of
    ``SchemaIssue`` records at :attr:`Severity.ERROR` or higher
    (and, when ``fail_on_warning`` is set, at :attr:`Severity.WARNING`).

    Fields:

    - ``passed``: whether validation passed.
    - ``observed`` / ``expected``: the inputs to validation (kept for
      downstream traceability).
    - ``schema_issues``: tuple of :class:`SchemaIssue` (immutable).
    - ``issues`` / ``warnings``: common typed issue/warning collections.
    - ``missing_required_columns`` / ``extra_columns`` /
      ``type_mismatches``: optional summary counters. The contract
      itself is the source of truth; the counters are a convenience
      for reporting.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    passed: bool = Field(..., description="Whether validation passed.")
    observed: ObservedSchema = Field(
        ...,
        description="ObservedSchema that was validated.",
    )
    expected: ExpectedSchema = Field(
        ...,
        description="ExpectedSchema that the observed was validated against.",
    )
    schema_issues: tuple[SchemaIssue, ...] = Field(
        default=(),
        description="Tuple of SchemaIssue raised during validation (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
    )
    missing_required_columns: tuple[ColumnName, ...] = Field(
        default=(),
        description="Convenience: required columns that were not observed.",
    )
    extra_columns: tuple[ColumnName, ...] = Field(
        default=(),
        description="Convenience: observed columns not declared in the expected schema.",
    )
    type_mismatches: tuple[ColumnName, ...] = Field(
        default=(),
        description="Convenience: columns whose physical/logical type did not match.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _passed_consistent_with_issues(self) -> "SchemaValidationReport":
        has_error = any(
            issue.severity in (Severity.ERROR, Severity.CRITICAL) for issue in self.schema_issues
        ) or any(issue.severity in (Severity.ERROR, Severity.CRITICAL) for issue in self.issues)
        if self.passed and has_error:
            raise ValueError(
                "SchemaValidationReport with passed=True must not contain ERROR-or-higher issues."
            )
        if not self.passed and not self.schema_issues and not self.issues:
            # If the report is not passed but has no issues, the caller
            # has produced a degenerate report (e.g. a fingerprint
            # mismatch or row-count bound violation). We allow it but
            # require that the convenience counters be present so the
            # cause is visible to consumers.
            if not (self.missing_required_columns or self.extra_columns or self.type_mismatches):
                raise ValueError(
                    "SchemaValidationReport with passed=False must include "
                    "at least one schema_issue, issue, or a non-empty "
                    "convenience summary (missing_required_columns, "
                    "extra_columns, or type_mismatches)."
                )
        return self

    @model_validator(mode="after")
    def _summary_columns_unique(self) -> "SchemaValidationReport":
        for field_name in (
            "missing_required_columns",
            "extra_columns",
            "type_mismatches",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(
                    f"SchemaValidationReport.{field_name} contains duplicate column names."
                )
        return self
