"""Tests for schema contracts (Build Queue v2.1 Task 22).

Covers:

- ``LogicalDataType`` / ``PhysicalDataType`` valid/invalid values.
- ``ColumnSchema`` / ``ObservedSchema`` / ``ExpectedColumnSchema`` /
  ``ExpectedSchema`` instantiation, invariants, and serialization
  round-trips.
- ``SchemaInferenceRequest`` and ``SchemaValidationRequest`` request
  shapes.
- ``SchemaValidationReport`` invariants: ``passed`` must be consistent
  with the presence of ERROR-or-higher issues, and a non-passed report
  must explain itself via either issues or convenience summaries.
- ``SchemaIssue`` validation and serialization.

These tests intentionally avoid importing any heavy compute library so
that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    Severity,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import (
    ColumnName,
    ColumnSchema,
    ExpectedColumnSchema,
    ExpectedSchema,
    LogicalDataType,
    ObservedSchema,
    PhysicalDataType,
    SchemaInferenceRequest,
    SchemaIssue,
    SchemaValidationReport,
    SchemaValidationRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle(name: str = "orders") -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name=name)


def _col(
    name: str = "id",
    physical: PhysicalDataType = PhysicalDataType.INT64,
    logical: LogicalDataType | None = LogicalDataType.INTEGER,
    nullable: bool | None = False,
) -> ColumnSchema:
    return ColumnSchema(
        name=name,
        physical_type=physical,
        logical_type=logical,
        nullable=nullable,
    )


# ---------------------------------------------------------------------------
# LogicalDataType / PhysicalDataType
# ---------------------------------------------------------------------------
class TestLogicalDataType:
    def test_known_members(self) -> None:
        assert LogicalDataType.INTEGER.value == "integer"
        assert LogicalDataType.FLOAT.value == "float"
        assert LogicalDataType.BOOLEAN.value == "boolean"
        assert LogicalDataType.STRING.value == "string"
        assert LogicalDataType.CATEGORICAL.value == "categorical"
        assert LogicalDataType.DATE.value == "date"
        assert LogicalDataType.DATETIME.value == "datetime"
        assert LogicalDataType.TIMEDELTA.value == "timedelta"
        assert LogicalDataType.BINARY.value == "binary"
        assert LogicalDataType.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            LogicalDataType("decimal")  # type: ignore[arg-type]


class TestPhysicalDataType:
    def test_known_members(self) -> None:
        assert PhysicalDataType.INT32.value == "int32"
        assert PhysicalDataType.INT64.value == "int64"
        assert PhysicalDataType.FLOAT64.value == "float64"
        assert PhysicalDataType.UTF8.value == "utf8"
        assert PhysicalDataType.TIMESTAMP.value == "timestamp"
        assert PhysicalDataType.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            PhysicalDataType("varchar")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ColumnSchema
# ---------------------------------------------------------------------------
class TestColumnSchema:
    def test_minimal(self) -> None:
        c = ColumnSchema(name="id", physical_type=PhysicalDataType.INT64)
        assert c.name == "id"
        assert c.physical_type is PhysicalDataType.INT64
        assert c.logical_type is None
        assert c.nullable is None
        assert c.ordinal is None

    def test_full(self) -> None:
        c = ColumnSchema(
            name="amount",
            physical_type=PhysicalDataType.FLOAT64,
            logical_type=LogicalDataType.FLOAT,
            nullable=True,
            ordinal=3,
            description="transaction amount",
            metadata={"unit": "USD"},
        )
        assert c.nullable is True
        assert c.ordinal == 3
        assert c.description == "transaction amount"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnSchema(name="", physical_type=PhysicalDataType.INT64)

    def test_negative_ordinal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnSchema(
                name="x", physical_type=PhysicalDataType.INT64, ordinal=-1
            )

    def test_round_trip(self) -> None:
        c = _col()
        assert ColumnSchema.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# ObservedSchema
# ---------------------------------------------------------------------------
class TestObservedSchema:
    def test_empty(self) -> None:
        s = ObservedSchema()
        assert s.columns == ()
        assert s.fingerprint is None
        assert s.row_count_estimate is None

    def test_with_columns(self) -> None:
        s = ObservedSchema(
            columns=(_col("id"), _col("name", PhysicalDataType.UTF8, LogicalDataType.STRING)),
            fingerprint="abc",
            row_count_estimate=100,
        )
        assert len(s.columns) == 2
        assert s.row_count_estimate == 100

    def test_duplicate_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ObservedSchema(columns=(_col("id"), _col("id")))

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ObservedSchema(row_count_estimate=-1)

    def test_round_trip(self) -> None:
        s = ObservedSchema(columns=(_col("id"),))
        assert ObservedSchema.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# ExpectedColumnSchema
# ---------------------------------------------------------------------------
class TestExpectedColumnSchema:
    def test_requires_at_least_one_type(self) -> None:
        with pytest.raises(ValidationError):
            ExpectedColumnSchema(name="id")

    def test_physical_only(self) -> None:
        c = ExpectedColumnSchema(
            name="id", physical_type=PhysicalDataType.INT64
        )
        assert c.physical_type is PhysicalDataType.INT64
        assert c.logical_type is None
        assert c.required is True

    def test_logical_only(self) -> None:
        c = ExpectedColumnSchema(name="id", logical_type=LogicalDataType.INTEGER)
        assert c.logical_type is LogicalDataType.INTEGER
        assert c.physical_type is None

    def test_both(self) -> None:
        c = ExpectedColumnSchema(
            name="id",
            physical_type=PhysicalDataType.INT64,
            logical_type=LogicalDataType.INTEGER,
            nullable=False,
            required=False,
        )
        assert c.required is False

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpectedColumnSchema(
                name="", physical_type=PhysicalDataType.INT64
            )

    def test_round_trip(self) -> None:
        c = ExpectedColumnSchema(
            name="id",
            physical_type=PhysicalDataType.INT64,
            logical_type=LogicalDataType.INTEGER,
        )
        assert ExpectedColumnSchema.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# ExpectedSchema
# ---------------------------------------------------------------------------
class TestExpectedSchema:
    def test_empty(self) -> None:
        s = ExpectedSchema()
        assert s.columns == ()
        assert s.strict_extra_columns is True
        assert s.min_row_count is None
        assert s.max_row_count is None

    def test_with_columns(self) -> None:
        s = ExpectedSchema(
            columns=(
                ExpectedColumnSchema(
                    name="id",
                    physical_type=PhysicalDataType.INT64,
                    logical_type=LogicalDataType.INTEGER,
                ),
            ),
            expected_fingerprint="abc",
            min_row_count=10,
            max_row_count=100,
            strict_extra_columns=False,
        )
        assert len(s.columns) == 1
        assert s.max_row_count == 100
        assert s.strict_extra_columns is False

    def test_duplicate_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpectedSchema(
                columns=(
                    ExpectedColumnSchema(
                        name="id", physical_type=PhysicalDataType.INT64
                    ),
                    ExpectedColumnSchema(
                        name="id", logical_type=LogicalDataType.INTEGER
                    ),
                ),
            )

    def test_row_count_bounds_inconsistent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpectedSchema(min_row_count=100, max_row_count=10)

    def test_row_count_bounds_equal_ok(self) -> None:
        s = ExpectedSchema(min_row_count=10, max_row_count=10)
        assert s.min_row_count == s.max_row_count

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpectedSchema(min_row_count=-1)

    def test_round_trip(self) -> None:
        s = ExpectedSchema(
            columns=(
                ExpectedColumnSchema(
                    name="id", logical_type=LogicalDataType.INTEGER
                ),
            ),
        )
        assert ExpectedSchema.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# SchemaIssue
# ---------------------------------------------------------------------------
class TestSchemaIssue:
    def test_minimal(self) -> None:
        i = SchemaIssue(
            code="SCHEMA_MISMATCH",
            severity=Severity.ERROR,
            message="bad type",
        )
        assert i.code == "SCHEMA_MISMATCH"
        assert i.column_name is None

    def test_full(self) -> None:
        i = SchemaIssue(
            code="SCHEMA_MISMATCH",
            severity=Severity.ERROR,
            message="bad type",
            column_name="amount",
            expected_physical_type=PhysicalDataType.FLOAT64,
            expected_logical_type=LogicalDataType.FLOAT,
            observed_physical_type=PhysicalDataType.UTF8,
            observed_logical_type=LogicalDataType.STRING,
            run_id="r1",
            stage_id="stage-validate",
            context={"k": "v"},
        )
        assert i.column_name == "amount"
        assert i.expected_physical_type is PhysicalDataType.FLOAT64

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaIssue(code="", severity=Severity.ERROR, message="m")

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaIssue(code="X", severity=Severity.ERROR, message="")

    def test_round_trip(self) -> None:
        i = SchemaIssue(
            code="X", severity=Severity.WARNING, message="m", column_name="c"
        )
        assert SchemaIssue.model_validate(i.model_dump(mode="json")) == i


# ---------------------------------------------------------------------------
# SchemaInferenceRequest
# ---------------------------------------------------------------------------
class TestSchemaInferenceRequest:
    def test_minimal(self) -> None:
        r = SchemaInferenceRequest(dataset=_handle())
        assert r.dataset is not None
        assert r.expected_fingerprint_hint is None
        assert r.max_columns is None
        assert r.sample_row_count is None

    def test_full(self) -> None:
        r = SchemaInferenceRequest(
            dataset=_handle(),
            expected_fingerprint_hint="abc",
            max_columns=100,
            sample_row_count=1000,
        )
        assert r.max_columns == 100

    def test_negative_max_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaInferenceRequest(dataset=_handle(), max_columns=-1)

    def test_negative_sample_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaInferenceRequest(dataset=_handle(), sample_row_count=-1)


# ---------------------------------------------------------------------------
# SchemaValidationRequest
# ---------------------------------------------------------------------------
def _observed() -> ObservedSchema:
    return ObservedSchema(
        columns=(_col("id"), _col("name", PhysicalDataType.UTF8, LogicalDataType.STRING)),
    )


def _expected() -> ExpectedSchema:
    return ExpectedSchema(
        columns=(
            ExpectedColumnSchema(
                name="id", physical_type=PhysicalDataType.INT64
            ),
            ExpectedColumnSchema(
                name="name", physical_type=PhysicalDataType.UTF8
            ),
        ),
    )


class TestSchemaValidationRequest:
    def test_minimal(self) -> None:
        r = SchemaValidationRequest(
            dataset=_handle(), observed=_observed(), expected=_expected()
        )
        assert r.fail_on_warning is False


# ---------------------------------------------------------------------------
# SchemaValidationReport
# ---------------------------------------------------------------------------
class TestSchemaValidationReport:
    def test_passed_with_no_issues(self) -> None:
        rep = SchemaValidationReport(
            passed=True, observed=_observed(), expected=_expected()
        )
        assert rep.passed is True
        assert rep.schema_issues == ()

    def test_passed_with_warnings_allowed(self) -> None:
        rep = SchemaValidationReport(
            passed=True,
            observed=_observed(),
            expected=_expected(),
            schema_issues=(
                SchemaIssue(
                    code="WARN",
                    severity=Severity.WARNING,
                    message="w",
                ),
            ),
        )
        assert rep.passed is True

    def test_passed_with_error_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaValidationReport(
                passed=True,
                observed=_observed(),
                expected=_expected(),
                schema_issues=(
                    SchemaIssue(
                        code="ERR",
                        severity=Severity.ERROR,
                        message="e",
                    ),
                ),
            )

    def test_failed_with_error_issue_ok(self) -> None:
        rep = SchemaValidationReport(
            passed=False,
            observed=_observed(),
            expected=_expected(),
            schema_issues=(
                SchemaIssue(
                    code="ERR",
                    severity=Severity.ERROR,
                    message="e",
                    column_name="amount",
                ),
            ),
        )
        assert rep.passed is False

    def test_failed_via_missing_columns_ok(self) -> None:
        rep = SchemaValidationReport(
            passed=False,
            observed=_observed(),
            expected=_expected(),
            missing_required_columns=("required_col",),
        )
        assert rep.passed is False
        assert rep.missing_required_columns == ("required_col",)

    def test_failed_via_extra_columns_ok(self) -> None:
        rep = SchemaValidationReport(
            passed=False,
            observed=_observed(),
            expected=_expected(),
            extra_columns=("surprise",),
        )
        assert rep.extra_columns == ("surprise",)

    def test_failed_via_type_mismatches_ok(self) -> None:
        rep = SchemaValidationReport(
            passed=False,
            observed=_observed(),
            expected=_expected(),
            type_mismatches=("amount",),
        )
        assert rep.type_mismatches == ("amount",)

    def test_failed_with_no_explanation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaValidationReport(
                passed=False,
                observed=_observed(),
                expected=_expected(),
            )

    def test_duplicate_summary_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SchemaValidationReport(
                passed=False,
                observed=_observed(),
                expected=_expected(),
                missing_required_columns=("a", "a"),
            )

    def test_round_trip(self) -> None:
        rep = SchemaValidationReport(
            passed=False,
            observed=_observed(),
            expected=_expected(),
            schema_issues=(
                SchemaIssue(
                    code="ERR",
                    severity=Severity.ERROR,
                    message="e",
                ),
            ),
        )
        assert SchemaValidationReport.model_validate(rep.model_dump(mode="json")) == rep


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_schemas_contracts_do_not_import_heavy_libs() -> None:
    """Importing the schemas contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.schemas as schemas_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by schemas contracts: {leaked}"
