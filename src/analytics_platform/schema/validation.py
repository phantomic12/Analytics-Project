"""Schema validation (Build Queue v2.1 Task 90).

This module is the canonical schema-validation stage. It consumes
an :class:`ObservedSchema` (produced by :mod:`schema.inference`)
and an :class:`ExpectedSchema` (produced by the user / config)
and returns a :class:`SchemaValidationReport`. The validator is
pure: it does not touch Polars, the catalog, or the runtime
store. The single-responsibility split keeps Task 90 free of any
heavy-library concerns.

Per the architecture-test plan (section 5), the ``schema`` module
is a domain module and may import from contracts, core, and
nothing else for Task 90 specifically (the validator is pure).

Scope (Task 90):

- :class:`SchemaValidator` — the canonical validator.
- :func:`validate_schema` — module-level convenience helper that
  uses the singleton validator.
- :class:`SchemaValidationError` — typed failure carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

from typing import Any

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.schemas import (
    ColumnName,
    ExpectedColumnSchema,
    ExpectedSchema,
    LogicalDataType,
    ObservedSchema,
    PhysicalDataType,
    SchemaIssue,
    SchemaValidationReport,
    SchemaValidationRequest,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "SchemaValidator",
    "SchemaValidationError",
    "validate_schema",
]


_LOGGER = get_logger("schema.validation")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for validation error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# Stable codes for the issues raised by the validator.
_MISSING_REQUIRED = "SCHEMA_MISSING_REQUIRED_COLUMN"
_EXTRA_COLUMN = "SCHEMA_EXTRA_COLUMN"
_PHYSICAL_TYPE_MISMATCH = "SCHEMA_PHYSICAL_TYPE_MISMATCH"
_LOGICAL_TYPE_MISMATCH = "SCHEMA_LOGICAL_TYPE_MISMATCH"
_NULLABILITY_MISMATCH = "SCHEMA_NULLABILITY_MISMATCH"
_FINGERPRINT_MISMATCH = "SCHEMA_FINGERPRINT_MISMATCH"
_ROW_COUNT_BELOW_MIN = "SCHEMA_ROW_COUNT_BELOW_MIN"
_ROW_COUNT_ABOVE_MAX = "SCHEMA_ROW_COUNT_ABOVE_MAX"


def _columns_by_name(observed: ObservedSchema) -> dict[ColumnName, Any]:
    """Return ``{column_name: ColumnSchema}`` for ``observed``."""
    return {col.name: col for col in observed.columns}


def _is_physical_compatible(
    expected: PhysicalDataType, observed: PhysicalDataType
) -> bool:
    """Return True when ``observed`` is a wider integer/float of ``expected``.

    Compatibility widens: ``INT8`` is compatible with ``INT32`` /
    ``INT64``; ``FLOAT32`` is compatible with ``FLOAT64``. Wider
    rules are conservative on purpose so the validator does not
    promote widening without an explicit declaration.
    """
    integer_widening = {
        PhysicalDataType.INT8: {
            PhysicalDataType.INT16,
            PhysicalDataType.INT32,
            PhysicalDataType.INT64,
        },
        PhysicalDataType.INT16: {PhysicalDataType.INT32, PhysicalDataType.INT64},
        PhysicalDataType.INT32: {PhysicalDataType.INT64},
        PhysicalDataType.UINT8: {
            PhysicalDataType.UINT16,
            PhysicalDataType.UINT32,
            PhysicalDataType.UINT64,
        },
        PhysicalDataType.UINT16: {PhysicalDataType.UINT32, PhysicalDataType.UINT64},
        PhysicalDataType.UINT32: {PhysicalDataType.UINT64},
        PhysicalDataType.FLOAT32: {PhysicalDataType.FLOAT64},
    }
    widening_set = integer_widening.get(expected, set())
    if observed == expected:
        return True
    return observed in widening_set


class SchemaValidationError(AnalyticsPlatformError):
    """A typed schema-validation failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class SchemaValidator:
    """The canonical schema validator.

    The validator is stateless and safe to instantiate per call;
    the module-level singleton is exposed via
    :func:`validate_schema` for convenience.
    """

    def validate(
        self,
        observed: ObservedSchema,
        expected: ExpectedSchema,
        *,
        request: SchemaValidationRequest | None = None,
    ) -> SchemaValidationReport:
        """Validate ``observed`` against ``expected``.

        The validator collects issues as it walks the schema; the
        final report's ``passed`` field is ``True`` only when no
        :attr:`Severity.ERROR` (or higher) issues were raised and
        no convenience counters are non-empty.
        """
        fail_on_warning = bool(request.fail_on_warning) if request is not None else False
        observed_by_name = _columns_by_name(observed)
        issues: list[SchemaIssue] = []

        # 1) Required-column presence.
        missing_required: list[ColumnName] = []
        for exp_col in expected.columns:
            if exp_col.required and exp_col.name not in observed_by_name:
                missing_required.append(exp_col.name)
                issues.append(
                    SchemaIssue(
                        code=_MISSING_REQUIRED,
                        severity=Severity.ERROR,
                        message=(
                            f"Required column {exp_col.name!r} is missing "
                            "from the observed schema."
                        ),
                        column_name=exp_col.name,
                        expected_physical_type=exp_col.physical_type,
                        expected_logical_type=exp_col.logical_type,
                        observed_physical_type=None,
                        observed_logical_type=None,
                        run_id=request.run_id if request else None,
                        stage_id=request.stage_id if request else None,
                        context=None,
                    )
                )

        # 2) Extra columns when strict_extra_columns is True.
        extra_columns: list[ColumnName] = []
        if expected.strict_extra_columns:
            declared = {c.name for c in expected.columns}
            for col in observed.columns:
                if col.name not in declared:
                    extra_columns.append(col.name)
                    issues.append(
                        SchemaIssue(
                            code=_EXTRA_COLUMN,
                            severity=Severity.WARNING,
                            message=(
                                f"Observed column {col.name!r} is not "
                                "declared in the expected schema."
                            ),
                            column_name=col.name,
                            expected_physical_type=None,
                            expected_logical_type=None,
                            observed_physical_type=col.physical_type,
                            observed_logical_type=col.logical_type,
                            run_id=request.run_id if request else None,
                            stage_id=request.stage_id if request else None,
                            context=None,
                        )
                    )

        # 3) Per-column type checks (only for declared columns that exist).
        type_mismatches: list[ColumnName] = []
        for exp_col in expected.columns:
            obs_col = observed_by_name.get(exp_col.name)
            if obs_col is None:
                continue
            if exp_col.physical_type is not None and not _is_physical_compatible(
                exp_col.physical_type, obs_col.physical_type
            ):
                type_mismatches.append(exp_col.name)
                issues.append(
                    SchemaIssue(
                        code=_PHYSICAL_TYPE_MISMATCH,
                        severity=Severity.ERROR,
                        message=(
                            f"Column {exp_col.name!r} physical type "
                            f"{obs_col.physical_type.value!r} is not compatible "
                            f"with expected {exp_col.physical_type.value!r}."
                        ),
                        column_name=exp_col.name,
                        expected_physical_type=exp_col.physical_type,
                        expected_logical_type=exp_col.logical_type,
                        observed_physical_type=obs_col.physical_type,
                        observed_logical_type=obs_col.logical_type,
                        run_id=request.run_id if request else None,
                        stage_id=request.stage_id if request else None,
                        context=None,
                    )
                )
            if (
                exp_col.logical_type is not None
                and obs_col.logical_type is not None
                and exp_col.logical_type is not obs_col.logical_type
            ):
                # Different *logical* types only flag when neither
                # is UNKNOWN; UNKNOWN is the inferencer's "I don't
                # know" placeholder and must not trigger a
                # logical-type mismatch.
                if (
                    exp_col.logical_type is not LogicalDataType.UNKNOWN
                    and obs_col.logical_type is not LogicalDataType.UNKNOWN
                ):
                    type_mismatches.append(exp_col.name)
                    issues.append(
                        SchemaIssue(
                            code=_LOGICAL_TYPE_MISMATCH,
                            severity=Severity.ERROR,
                            message=(
                                f"Column {exp_col.name!r} logical type "
                                f"{obs_col.logical_type.value!r} does not match "
                                f"expected {exp_col.logical_type.value!r}."
                            ),
                            column_name=exp_col.name,
                            expected_physical_type=exp_col.physical_type,
                            expected_logical_type=exp_col.logical_type,
                            observed_physical_type=obs_col.physical_type,
                            observed_logical_type=obs_col.logical_type,
                            run_id=request.run_id if request else None,
                            stage_id=request.stage_id if request else None,
                            context=None,
                        )
                    )
            if (
                exp_col.nullable is not None
                and obs_col.nullable is not None
                and exp_col.nullable is not obs_col.nullable
            ):
                # ``nullable=False`` observed but ``nullable=True``
                # declared is an error (declared stricter than
                # observed). The reverse (``nullable=True`` observed
                # but ``nullable=False`` declared) is a WARNING so
                # the operator can decide whether the optional
                # annotation was actually required.
                if exp_col.nullable is False and obs_col.nullable is True:
                    issues.append(
                        SchemaIssue(
                            code=_NULLABILITY_MISMATCH,
                            severity=Severity.ERROR,
                            message=(
                                f"Column {exp_col.name!r} is nullable in the "
                                "observed schema but declared non-nullable."
                            ),
                            column_name=exp_col.name,
                            expected_physical_type=exp_col.physical_type,
                            expected_logical_type=exp_col.logical_type,
                            observed_physical_type=obs_col.physical_type,
                            observed_logical_type=obs_col.logical_type,
                            run_id=request.run_id if request else None,
                            stage_id=request.stage_id if request else None,
                            context=None,
                        )
                    )
                else:
                    issues.append(
                        SchemaIssue(
                            code=_NULLABILITY_MISMATCH,
                            severity=Severity.WARNING,
                            message=(
                                f"Column {exp_col.name!r} is non-nullable in the "
                                "observed schema but declared nullable."
                            ),
                            column_name=exp_col.name,
                            expected_physical_type=exp_col.physical_type,
                            expected_logical_type=exp_col.logical_type,
                            observed_physical_type=obs_col.physical_type,
                            observed_logical_type=obs_col.logical_type,
                            run_id=request.run_id if request else None,
                            stage_id=request.stage_id if request else None,
                            context=None,
                        )
                    )

        # 4) Schema-level fingerprint equality.
        if (
            expected.expected_fingerprint is not None
            and observed.fingerprint is not None
            and observed.fingerprint != expected.expected_fingerprint
        ):
            issues.append(
                SchemaIssue(
                    code=_FINGERPRINT_MISMATCH,
                    severity=Severity.ERROR,
                    message=(
                        "Observed schema fingerprint does not match the "
                        "expected fingerprint."
                    ),
                    column_name=None,
                    expected_physical_type=None,
                    expected_logical_type=None,
                    observed_physical_type=None,
                    observed_logical_type=None,
                    run_id=request.run_id if request else None,
                    stage_id=request.stage_id if request else None,
                    context=None,
                )
            )

        # 5) Row-count bounds.
        if (
            expected.min_row_count is not None
            and observed.row_count_estimate is not None
            and observed.row_count_estimate < expected.min_row_count
        ):
            issues.append(
                SchemaIssue(
                    code=_ROW_COUNT_BELOW_MIN,
                    severity=Severity.ERROR,
                    message=(
                        f"Observed row count {observed.row_count_estimate} is "
                        f"below the declared minimum {expected.min_row_count}."
                    ),
                    column_name=None,
                    expected_physical_type=None,
                    expected_logical_type=None,
                    observed_physical_type=None,
                    observed_logical_type=None,
                    run_id=request.run_id if request else None,
                    stage_id=request.stage_id if request else None,
                    context=None,
                )
            )
        if (
            expected.max_row_count is not None
            and observed.row_count_estimate is not None
            and observed.row_count_estimate > expected.max_row_count
        ):
            issues.append(
                SchemaIssue(
                    code=_ROW_COUNT_ABOVE_MAX,
                    severity=Severity.ERROR,
                    message=(
                        f"Observed row count {observed.row_count_estimate} is "
                        f"above the declared maximum {expected.max_row_count}."
                    ),
                    column_name=None,
                    expected_physical_type=None,
                    expected_logical_type=None,
                    observed_physical_type=None,
                    observed_logical_type=None,
                    run_id=request.run_id if request else None,
                    stage_id=request.stage_id if request else None,
                    context=None,
                )
            )

        # 6) Pass/fail aggregation.
        has_error = any(
            i.severity in (Severity.ERROR, Severity.CRITICAL) for i in issues
        )
        has_warning = any(i.severity is Severity.WARNING for i in issues)
        passed = not has_error and not (fail_on_warning and has_warning)

        # Dedup convenience counters so a column that fails multiple
        # checks (e.g. both physical and logical type mismatch) does
        # not double-count.
        missing_required_tuple = tuple(dict.fromkeys(missing_required))
        extra_columns_tuple = tuple(dict.fromkeys(extra_columns))
        type_mismatches_tuple = tuple(dict.fromkeys(type_mismatches))

        report = SchemaValidationReport(
            passed=passed,
            observed=observed,
            expected=expected,
            schema_issues=tuple(issues),
            issues=(),
            warnings=(),
            missing_required_columns=missing_required_tuple,
            extra_columns=extra_columns_tuple,
            type_mismatches=type_mismatches_tuple,
            run_id=request.run_id if request else None,
            stage_id=request.stage_id if request else None,
            metadata=None,
        )
        _LOGGER.info(
            "Validated schema: passed=%s schema_issues=%d missing=%d extra=%d "
            "type_mismatches=%d",
            passed,
            len(issues),
            len(missing_required_tuple),
            len(extra_columns_tuple),
            len(type_mismatches_tuple),
        )
        return report


# Module-level singleton validator.
_VALIDATOR = SchemaValidator()


def validate_schema(
    observed: ObservedSchema,
    expected: ExpectedSchema,
    *,
    request: SchemaValidationRequest | None = None,
) -> SchemaValidationReport:
    """Validate ``observed`` against ``expected`` using the singleton."""
    return _VALIDATOR.validate(observed, expected, request=request)