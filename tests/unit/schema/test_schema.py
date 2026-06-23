"""Tests for the schema inference and validation stages (Build Queue v2.1 Tasks 89-90)."""

from __future__ import annotations

from typing import Any

import pytest

from analytics_platform.contracts.common import Severity
from analytics_platform.contracts.schemas import (
    ColumnSchema,
    ColumnName,
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
from analytics_platform.schema import (
    SchemaInferenceError,
    SchemaInferencer,
    SchemaValidationError,
    SchemaValidator,
    infer_schema,
    validate_schema,
)
from analytics_platform.schema.inference import map_physical_to_logical


# ===========================================================================
# Task 89 — schema inference
# ===========================================================================
class TestPhysicalToLogicalMapping:
    @pytest.mark.parametrize(
        "physical, expected",
        [
            (PhysicalDataType.INT8, LogicalDataType.INTEGER),
            (PhysicalDataType.INT32, LogicalDataType.INTEGER),
            (PhysicalDataType.UINT64, LogicalDataType.INTEGER),
            (PhysicalDataType.FLOAT32, LogicalDataType.FLOAT),
            (PhysicalDataType.FLOAT64, LogicalDataType.FLOAT),
            (PhysicalDataType.BOOL, LogicalDataType.BOOLEAN),
            (PhysicalDataType.UTF8, LogicalDataType.STRING),
            (PhysicalDataType.LARGE_UTF8, LogicalDataType.STRING),
            (PhysicalDataType.DATE32, LogicalDataType.DATE),
            (PhysicalDataType.DATE64, LogicalDataType.DATE),
            (PhysicalDataType.TIMESTAMP, LogicalDataType.DATETIME),
            (PhysicalDataType.BINARY, LogicalDataType.BINARY),
            (PhysicalDataType.LIST, LogicalDataType.UNKNOWN),
            (PhysicalDataType.STRUCT, LogicalDataType.UNKNOWN),
            (PhysicalDataType.NULL, LogicalDataType.UNKNOWN),
        ],
    )
    def test_mapping(self, physical: PhysicalDataType, expected: LogicalDataType) -> None:
        assert map_physical_to_logical(physical) is expected


class TestSchemaInferencer:
    def test_infer_from_iterable(self) -> None:
        obs = infer_schema(
            [
                ("id", "int64", False),
                ("name", "utf8", True),
                ("score", "float64", True),
            ]
        )
        assert [c.name for c in obs.columns] == ["id", "name", "score"]
        assert [c.physical_type for c in obs.columns] == [
            PhysicalDataType.INT64,
            PhysicalDataType.UTF8,
            PhysicalDataType.FLOAT64,
        ]
        assert [c.logical_type for c in obs.columns] == [
            LogicalDataType.INTEGER,
            LogicalDataType.STRING,
            LogicalDataType.FLOAT,
        ]

    def test_infer_from_mapping(self) -> None:
        obs = infer_schema({"a": "int32", "b": "bool"})
        assert [c.name for c in obs.columns] == ["a", "b"]
        assert obs.columns[0].physical_type is PhysicalDataType.INT32
        assert obs.columns[1].logical_type is LogicalDataType.BOOLEAN

    def test_infer_from_polars_like_mapping(self) -> None:
        class _FauxSchema(dict):
            pass

        schema = _FauxSchema(
            [("id", "int64"), ("flag", "bool"), ("label", "large_utf8")]
        )
        obs = infer_schema(schema)
        assert obs.columns[0].physical_type is PhysicalDataType.INT64
        assert obs.columns[1].physical_type is PhysicalDataType.BOOL
        assert obs.columns[2].physical_type is PhysicalDataType.LARGE_UTF8
        assert obs.columns[2].logical_type is LogicalDataType.STRING

    def test_infer_from_fake_polars_frame(self) -> None:
        class _FauxDType:
            def __init__(self, label: str) -> None:
                self._label = label

            def __str__(self) -> str:
                return self._label

        class _FauxSchema:
            def __init__(self, items: list[tuple[str, _FauxDType]]) -> None:
                self._items = items

            def items(self) -> list[tuple[str, _FauxDType]]:
                return self._items

        class _FauxFrame:
            def __init__(self) -> None:
                self.schema = _FauxSchema(
                    [("id", _FauxDType("int64")), ("name", _FauxDType("utf8"))]
                )
                self.height = 42

        frame = _FauxFrame()
        obs = infer_schema(frame)
        assert obs.row_count_estimate == 42
        assert [c.name for c in obs.columns] == ["id", "name"]
        assert obs.fingerprint is not None

    def test_fingerprint_is_stable_across_orders(self) -> None:
        a = infer_schema([("a", "int64"), ("b", "utf8")])
        b = infer_schema([("b", "utf8"), ("a", "int64")])
        assert a.fingerprint == b.fingerprint

    def test_fingerprint_changes_with_types(self) -> None:
        a = infer_schema([("a", "int64")])
        b = infer_schema([("a", "utf8")])
        assert a.fingerprint != b.fingerprint

    def test_max_columns_truncates(self) -> None:
        inf = SchemaInferencer(max_columns=2)
        obs = inf.infer([("a", "int64"), ("b", "utf8"), ("c", "float64")])
        assert [c.name for c in obs.columns] == ["a", "b"]

    def test_max_columns_zero_returns_empty(self) -> None:
        inf = SchemaInferencer(max_columns=0)
        obs = inf.infer([("a", "int64")])
        assert obs.columns == ()

    def test_request_overrides_construction(self) -> None:
        from analytics_platform.contracts.datasets import (
            DatasetFormat,
            DatasetHandle,
            DatasetMaterializationStatus,
            DatasetRef,
            DatasetRole,
            StorageBackend,
        )

        handle = DatasetHandle(
            dataset_id="d1",
            dataset_ref=DatasetRef("ds-d1"),
            name="d1",
            format=DatasetFormat.PARQUET,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.MATERIALIZED,
        )
        inf = SchemaInferencer(max_columns=10)
        request = SchemaInferenceRequest(
            dataset=handle,
            max_columns=1,
            sample_row_count=None,
            run_id=None,
            stage_id=None,
        )
        obs = inf.infer(
            [("a", "int64"), ("b", "utf8"), ("c", "float64")], request=request
        )
        assert [c.name for c in obs.columns] == ["a"]

    def test_negative_max_columns_rejected(self) -> None:
        with pytest.raises(SchemaInferenceError) as ei:
            SchemaInferencer(max_columns=-1)
        assert ei.value.issue.code == "SCHEMA_INFERENCE_BAD_MAX_COLUMNS"

    def test_negative_sample_row_count_rejected(self) -> None:
        with pytest.raises(SchemaInferenceError) as ei:
            SchemaInferencer(sample_row_count=-1)
        assert ei.value.issue.code == "SCHEMA_INFERENCE_BAD_SAMPLE_ROW_COUNT"

    def test_unsupported_frame_type_raises(self) -> None:
        with pytest.raises(SchemaInferenceError) as ei:
            infer_schema(42)
        assert ei.value.issue.code == "SCHEMA_INFERENCE_UNSUPPORTED_FRAME"

    def test_bad_row_length_raises(self) -> None:
        with pytest.raises(SchemaInferenceError) as ei:
            infer_schema([("a",)])  # type: ignore[list-item]
        assert ei.value.issue.code == "SCHEMA_INFERENCE_BAD_ROW"

    def test_unknown_dtype_falls_back_to_unknown(self) -> None:
        obs = infer_schema([("a", "frobnitz")])
        assert obs.columns[0].physical_type is PhysicalDataType.UNKNOWN
        assert obs.columns[0].logical_type is LogicalDataType.UNKNOWN

    def test_observed_columns_are_typed(self) -> None:
        obs = infer_schema([("a", "int64")])
        assert obs.columns[0].ordinal == 0


# ===========================================================================
# Task 90 — schema validation
# ===========================================================================
def _observed(columns: list[tuple[str, str, bool | None]]) -> ObservedSchema:
    obs = infer_schema(columns)
    return obs


def _expected(
    columns: list[tuple[str, str, str | None, bool, bool]],
    *,
    strict: bool = True,
    min_rows: int | None = None,
    max_rows: int | None = None,
    fingerprint: str | None = None,
) -> ExpectedSchema:
    out: list[ExpectedColumnSchema] = []
    for name, physical, logical, required, nullable in columns:
        out.append(
            ExpectedColumnSchema(
                name=name,
                physical_type=PhysicalDataType(physical) if physical else None,
                logical_type=LogicalDataType(logical) if logical else None,
                required=required,
                nullable=nullable,
                description=None,
                metadata=None,
            )
        )
    return ExpectedSchema(
        columns=tuple(out),
        expected_fingerprint=fingerprint,
        min_row_count=min_rows,
        max_row_count=max_rows,
        strict_extra_columns=strict,
        description=None,
        metadata=None,
    )


class TestSchemaValidatorHappyPath:
    def test_passes_when_all_columns_match(self) -> None:
        obs = _observed([("id", "int64", False), ("name", "utf8", True)])
        expected = _expected(
            [
                ("id", "int64", "integer", True, False),
                ("name", "utf8", "string", True, True),
            ]
        )
        report = validate_schema(obs, expected)
        assert report.passed is True
        assert report.schema_issues == ()

    def test_int8_compatible_with_int32(self) -> None:
        obs = _observed([("a", "int32", False)])
        expected = _expected([("a", "int8", "integer", True, False)])
        report = validate_schema(obs, expected)
        assert report.passed is True

    def test_extra_columns_tolerated_when_not_strict(self) -> None:
        obs = _observed([("id", "int64", False), ("extra", "utf8", True)])
        expected = _expected(
            [("id", "int64", "integer", True, False)], strict=False
        )
        report = validate_schema(obs, expected)
        assert report.passed is True
        assert report.extra_columns == ()


class TestSchemaValidatorFailures:
    def test_missing_required_column_is_error(self) -> None:
        obs = _observed([("id", "int64", False)])
        expected = _expected(
            [
                ("id", "int64", "integer", True, False),
                ("name", "utf8", "string", True, True),
            ]
        )
        report = validate_schema(obs, expected)
        assert report.passed is False
        assert "name" in report.missing_required_columns
        assert any(
            i.code == "SCHEMA_MISSING_REQUIRED_COLUMN" for i in report.schema_issues
        )

    def test_extra_column_is_warning_when_strict(self) -> None:
        obs = _observed([("id", "int64", False), ("extra", "utf8", True)])
        expected = _expected(
            [("id", "int64", "integer", True, False)], strict=True
        )
        report = validate_schema(obs, expected)
        assert "extra" in report.extra_columns
        assert any(
            i.code == "SCHEMA_EXTRA_COLUMN" and i.severity is Severity.WARNING
            for i in report.schema_issues
        )

    def test_physical_type_mismatch(self) -> None:
        obs = _observed([("a", "utf8", False)])
        expected = _expected([("a", "int64", "integer", True, False)])
        report = validate_schema(obs, expected)
        assert report.passed is False
        assert "a" in report.type_mismatches
        assert any(
            i.code == "SCHEMA_PHYSICAL_TYPE_MISMATCH" for i in report.schema_issues
        )

    def test_logical_type_mismatch(self) -> None:
        obs = _observed([("a", "int64", False)])
        expected = _expected([("a", "int64", "string", True, False)])
        report = validate_schema(obs, expected)
        assert report.passed is False
        assert any(
            i.code == "SCHEMA_LOGICAL_TYPE_MISMATCH" for i in report.schema_issues
        )

    def test_logical_unknown_does_not_trigger_mismatch(self) -> None:
        # Logical "unknown" must not raise a logical-type mismatch.
        obs = _observed([("a", "int64", False)])
        expected = _expected([("a", "int64", None, True, False)])
        report = validate_schema(obs, expected)
        assert all(
            i.code != "SCHEMA_LOGICAL_TYPE_MISMATCH" for i in report.schema_issues
        )

    def test_nullable_declared_false_but_observed_true_is_error(self) -> None:
        obs = _observed([("a", "int64", True)])
        expected = _expected([("a", "int64", "integer", True, False)])
        report = validate_schema(obs, expected)
        assert report.passed is False
        assert any(
            i.code == "SCHEMA_NULLABILITY_MISMATCH"
            and i.severity is Severity.ERROR
            for i in report.schema_issues
        )

    def test_nullable_declared_true_but_observed_false_is_warning(self) -> None:
        obs = _observed([("a", "int64", False)])
        expected = _expected([("a", "int64", "integer", True, True)])
        report = validate_schema(obs, expected)
        # WARNING does not fail the report.
        assert report.passed is True
        assert any(
            i.code == "SCHEMA_NULLABILITY_MISMATCH"
            and i.severity is Severity.WARNING
            for i in report.schema_issues
        )

    def test_nullable_unknown_in_observed_or_expected_no_op(self) -> None:
        # Build an ObservedSchema directly with nullable=None so the
        # validator cannot compare. Expected has explicit nullable=False.
        observed = ObservedSchema(
            columns=(
                ColumnSchema(
                    name="a",
                    physical_type=PhysicalDataType.INT64,
                    logical_type=LogicalDataType.INTEGER,
                    nullable=None,
                    ordinal=0,
                    description=None,
                    metadata=None,
                ),
            ),
            fingerprint="abc",
            row_count_estimate=None,
            notes=None,
            metadata=None,
        )
        expected = _expected([("a", "int64", "integer", True, False)])
        report = validate_schema(observed, expected)
        assert all(
            i.code != "SCHEMA_NULLABILITY_MISMATCH" for i in report.schema_issues
        )

    def test_fingerprint_mismatch_is_error(self) -> None:
        obs = _observed([("a", "int64", False)])
        expected = _expected(
            [("a", "int64", "integer", True, False)],
            fingerprint="not-the-actual-fp",
        )
        report = validate_schema(obs, expected)
        assert report.passed is False
        assert any(
            i.code == "SCHEMA_FINGERPRINT_MISMATCH" for i in report.schema_issues
        )

    def test_row_count_below_min_is_error(self) -> None:
        obs = _observed([("a", "int64", False)])
        # Inject a row_count_estimate by constructing manually.
        observed_with_count = obs.model_copy(
            update={"row_count_estimate": 5}
        )
        expected = _expected(
            [("a", "int64", "integer", True, False)],
            min_rows=10,
        )
        report = validate_schema(observed_with_count, expected)
        assert report.passed is False
        assert any(
            i.code == "SCHEMA_ROW_COUNT_BELOW_MIN" for i in report.schema_issues
        )

    def test_row_count_above_max_is_error(self) -> None:
        obs = _observed([("a", "int64", False)])
        observed_with_count = obs.model_copy(
            update={"row_count_estimate": 50}
        )
        expected = _expected(
            [("a", "int64", "integer", True, False)],
            max_rows=10,
        )
        report = validate_schema(observed_with_count, expected)
        assert report.passed is False
        assert any(
            i.code == "SCHEMA_ROW_COUNT_ABOVE_MAX" for i in report.schema_issues
        )

    def test_fail_on_warning_promotes_warnings_to_failure(self) -> None:
        obs = _observed([("id", "int64", False), ("extra", "utf8", True)])
        expected = _expected(
            [("id", "int64", "integer", True, False)], strict=True
        )
        report = validate_schema(
            obs,
            expected,
            request=SchemaValidationRequest(
                dataset=_handle(),  # type: ignore[arg-type]
                observed=obs,
                expected=expected,
                fail_on_warning=True,
            ),
        )
        assert report.passed is False

    def test_counter_columns_are_unique(self) -> None:
        obs = _observed(
            [("a", "int64", False), ("b", "utf8", True), ("c", "float64", False)]
        )
        # Declare a with a non-existent physical type to trigger
        # both physical AND logical mismatch on the same column.
        # That causes 'a' to appear twice in type_mismatches; the
        # validator must dedup.
        observed = obs.model_copy(
            update={
                "columns": tuple(
                    col.model_copy(update={"logical_type": LogicalDataType.STRING})
                    if col.name == "a"
                    else col
                    for col in obs.columns
                )
            }
        )
        expected = _expected(
            [
                ("a", "int64", "integer", True, False),
                ("b", "utf8", "string", True, True),
                ("c", "float64", "float", True, False),
            ]
        )
        report = validate_schema(observed, expected)
        assert report.type_mismatches.count(ColumnName("a")) == 1

    def test_validator_constructor_is_stateless(self) -> None:
        obs = _observed([("a", "int64", False)])
        expected = _expected([("a", "int64", "integer", True, False)])
        v = SchemaValidator()
        r1 = v.validate(obs, expected)
        r2 = v.validate(obs, expected)
        assert r1.passed == r2.passed
        assert len(r1.schema_issues) == len(r2.schema_issues)


def _handle() -> Any:
    from analytics_platform.contracts.datasets import (
        DatasetFormat,
        DatasetHandle,
        DatasetMaterializationStatus,
        DatasetRef,
        DatasetRole,
        StorageBackend,
    )

    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )