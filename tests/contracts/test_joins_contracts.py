"""Tests for join contracts (Build Queue v2.1 Task 27).

Covers:

- ``JoinType`` / ``JoinCardinality`` / ``JoinRiskLevel`` /
  ``JoinApprovalStatus`` / ``ColumnConflictPolicy`` /
  ``NullKeyPolicy`` / ``DuplicateKeyPolicy`` valid/invalid values.
- ``JoinKeySpec`` / ``JoinSpec`` invariants (datasets differ, keys
  unique).
- ``JoinValidationRequest`` defaults and bounded fields.
- ``JoinValidationReport`` invariants: ``BLOCKED`` requires a
  non-empty ``block_reason``; non-``BLOCKED`` forbids
  ``block_reason``; join-induced missingness ratios in
  ``[0.0, 1.0]``; column-conflict column names unique;
  ``computed_at`` coerced to UTC.
- ``JoinExecutionRequest`` invariants: ``explicit_override=True``
  requires a non-empty ``override_reason``; ``APPROVED`` /
  ``CONDITIONALLY_APPROVED`` validation reports can execute
  without an override; ``BLOCKED`` reports require an override.
- ``JoinExecutionReport`` invariants: timezone coercion for
  ``started_at`` / ``finished_at``.
- ``JoinedDatasetResult`` invariants: left/right dataset ids
  differ; key column lengths match; column-conflict column names
  unique; ``produced_at`` coerced to UTC.

These tests intentionally avoid importing any heavy compute library
so that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    ExecutionStatus,
    Issue,
    LineageId,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.joins import (
    ColumnConflictPolicy,
    DuplicateKeyPolicy,
    JoinApprovalStatus,
    JoinCardinality,
    JoinExecutionReport,
    JoinExecutionRequest,
    JoinKeySpec,
    JoinRiskLevel,
    JoinSpec,
    JoinType,
    JoinValidationReport,
    JoinValidationRequest,
    JoinedDatasetResult,
    NullKeyPolicy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _left() -> DatasetHandle:
    return DatasetHandle(dataset_id="left", dataset_ref="ds-left", name="orders")


def _right() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="right", dataset_ref="ds-right", name="customers"
    )


def _spec(
    *,
    left: DatasetHandle | None = None,
    right: DatasetHandle | None = None,
    keys: tuple[JoinKeySpec, ...] | None = None,
) -> JoinSpec:
    return JoinSpec(
        left_dataset=left or _left(),
        right_dataset=right or _right(),
        keys=keys or (JoinKeySpec(left_column="id", right_column="customer_id"),),
    )


def _validation_report(
    *,
    approval_status: JoinApprovalStatus = JoinApprovalStatus.APPROVED,
    risk_level: JoinRiskLevel = JoinRiskLevel.LOW,
    block_reason: str | None = None,
) -> JoinValidationReport:
    return JoinValidationReport(
        spec=_spec(),
        approval_status=approval_status,
        risk_level=risk_level,
        block_reason=block_reason,
    )


# ---------------------------------------------------------------------------
# Join enums
# ---------------------------------------------------------------------------
class TestJoinEnums:
    def test_join_type_known_members(self) -> None:
        assert JoinType.INNER.value == "inner"
        assert JoinType.LEFT.value == "left"
        assert JoinType.RIGHT.value == "right"
        assert JoinType.FULL_OUTER.value == "full_outer"
        assert JoinType.CROSS.value == "cross"

    def test_join_cardinality_known_members(self) -> None:
        assert JoinCardinality.ONE_TO_ONE.value == "one_to_one"
        assert JoinCardinality.MANY_TO_MANY.value == "many_to_many"

    def test_join_risk_level_known_members(self) -> None:
        assert JoinRiskLevel.LOW.value == "low"
        assert JoinRiskLevel.MEDIUM.value == "medium"
        assert JoinRiskLevel.HIGH.value == "high"

    def test_join_approval_status_known_members(self) -> None:
        assert JoinApprovalStatus.APPROVED.value == "approved"
        assert JoinApprovalStatus.CONDITIONALLY_APPROVED.value == "conditionally_approved"
        assert JoinApprovalStatus.BLOCKED.value == "blocked"

    def test_column_conflict_policy_known_members(self) -> None:
        assert ColumnConflictPolicy.RENAME.value == "rename"
        assert ColumnConflictPolicy.DROP_RIGHT.value == "drop_right"
        assert ColumnConflictPolicy.COALESCE.value == "coalesce"
        assert ColumnConflictPolicy.ERROR.value == "error"

    def test_null_key_policy_known_members(self) -> None:
        assert NullKeyPolicy.EXCLUDE.value == "exclude"
        assert NullKeyPolicy.KEEP.value == "keep"
        assert NullKeyPolicy.ERROR.value == "error"

    def test_duplicate_key_policy_known_members(self) -> None:
        assert DuplicateKeyPolicy.ALLOW.value == "allow"
        assert DuplicateKeyPolicy.DEDUPE.value == "dedupe"
        assert DuplicateKeyPolicy.ERROR.value == "error"

    def test_invalid_values_rejected(self) -> None:
        with pytest.raises(ValueError):
            JoinType("hash_join")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            JoinApprovalStatus("rejected")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# JoinSpec / JoinKeySpec
# ---------------------------------------------------------------------------
class TestJoinSpec:
    def test_basic(self) -> None:
        s = _spec()
        assert s.join_type is JoinType.INNER
        assert len(s.keys) == 1

    def test_datasets_differ(self) -> None:
        with pytest.raises(ValidationError):
            _spec(left=_left(), right=_left())

    def test_empty_keys_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinSpec(left_dataset=_left(), right_dataset=_right(), keys=())

    def test_duplicate_keys_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _spec(
                keys=(
                    JoinKeySpec(left_column="id", right_column="cid"),
                    JoinKeySpec(left_column="id", right_column="cid"),
                ),
            )

    def test_full(self) -> None:
        s = JoinSpec(
            left_dataset=_left(),
            right_dataset=_right(),
            join_type=JoinType.LEFT,
            keys=(JoinKeySpec(left_column="id", right_column="customer_id"),),
            left_role="target",
            right_role="feature",
            column_conflict_policy=ColumnConflictPolicy.COALESCE,
            null_key_policy=NullKeyPolicy.KEEP,
            duplicate_key_policy=DuplicateKeyPolicy.DEDUPE,
            expected_cardinality=JoinCardinality.MANY_TO_ONE,
        )
        assert s.expected_cardinality is JoinCardinality.MANY_TO_ONE


# ---------------------------------------------------------------------------
# JoinValidationRequest
# ---------------------------------------------------------------------------
class TestJoinValidationRequest:
    def test_basic(self) -> None:
        r = JoinValidationRequest(spec=_spec())
        assert r.max_join_induced_missingness_ratio == 0.1
        assert r.fail_on_high_risk is True

    def test_ratio_bounds(self) -> None:
        JoinValidationRequest(spec=_spec(), max_join_induced_missingness_ratio=0.0)
        JoinValidationRequest(spec=_spec(), max_join_induced_missingness_ratio=1.0)

    def test_ratio_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinValidationRequest(
                spec=_spec(), max_join_induced_missingness_ratio=1.5
            )


# ---------------------------------------------------------------------------
# JoinValidationReport
# ---------------------------------------------------------------------------
class TestJoinValidationReport:
    def test_minimal(self) -> None:
        r = _validation_report()
        assert r.column_conflict_policy is ColumnConflictPolicy.RENAME

    def test_blocked_requires_block_reason(self) -> None:
        with pytest.raises(ValidationError):
            JoinValidationReport(
                spec=_spec(),
                approval_status=JoinApprovalStatus.BLOCKED,
                risk_level=JoinRiskLevel.HIGH,
            )

    def test_blocked_with_reason_ok(self) -> None:
        r = JoinValidationReport(
            spec=_spec(),
            approval_status=JoinApprovalStatus.BLOCKED,
            risk_level=JoinRiskLevel.HIGH,
            block_reason="many-to-many cardinality detected",
        )
        assert r.block_reason is not None

    def test_non_blocked_forbids_block_reason(self) -> None:
        with pytest.raises(ValidationError):
            JoinValidationReport(
                spec=_spec(),
                approval_status=JoinApprovalStatus.APPROVED,
                risk_level=JoinRiskLevel.LOW,
                block_reason="not actually blocked",
            )

    def test_join_induced_missingness_ratio_bounds(self) -> None:
        with pytest.raises(ValidationError):
            JoinValidationReport(
                spec=_spec(),
                approval_status=JoinApprovalStatus.APPROVED,
                risk_level=JoinRiskLevel.LOW,
                join_induced_missingness=(("col", 1.5),),
            )

    def test_duplicate_column_conflicts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinValidationReport(
                spec=_spec(),
                approval_status=JoinApprovalStatus.APPROVED,
                risk_level=JoinRiskLevel.LOW,
                column_conflicts=(
                    ("col", ColumnConflictPolicy.RENAME),
                    ("col", ColumnConflictPolicy.DROP_RIGHT),
                ),
            )

    def test_naive_computed_at_normalized(self) -> None:
        r = JoinValidationReport(
            spec=_spec(),
            approval_status=JoinApprovalStatus.APPROVED,
            risk_level=JoinRiskLevel.LOW,
            computed_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.computed_at is not None
        assert r.computed_at.tzinfo is timezone.utc

    def test_with_warnings_and_issues(self) -> None:
        r = JoinValidationReport(
            spec=_spec(),
            approval_status=JoinApprovalStatus.CONDITIONALLY_APPROVED,
            risk_level=JoinRiskLevel.MEDIUM,
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
        )
        assert len(r.issues) == 1

    def test_round_trip(self) -> None:
        r = _validation_report()
        assert JoinValidationReport.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# JoinExecutionRequest
# ---------------------------------------------------------------------------
def _result() -> JoinedDatasetResult:
    return JoinedDatasetResult(
        result_dataset=DatasetHandle(
            dataset_id="joined", dataset_ref="ds-joined", name="orders_with_customers"
        ),
        left_dataset_id="left",
        right_dataset_id="right",
    )


class TestJoinExecutionRequest:
    def test_approved_executes_without_override(self) -> None:
        r = JoinExecutionRequest(validation_report=_validation_report())
        assert r.explicit_override is False

    def test_blocked_requires_override(self) -> None:
        with pytest.raises(ValidationError):
            JoinExecutionRequest(
                validation_report=_validation_report(
                    approval_status=JoinApprovalStatus.BLOCKED,
                    risk_level=JoinRiskLevel.HIGH,
                    block_reason="blocked",
                )
            )

    def test_blocked_with_override_ok(self) -> None:
        r = JoinExecutionRequest(
            validation_report=_validation_report(
                approval_status=JoinApprovalStatus.BLOCKED,
                risk_level=JoinRiskLevel.HIGH,
                block_reason="blocked",
            ),
            explicit_override=True,
            override_reason="manual review approved",
        )
        assert r.explicit_override is True

    def test_override_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            JoinExecutionRequest(
                validation_report=_validation_report(
                    approval_status=JoinApprovalStatus.BLOCKED,
                    risk_level=JoinRiskLevel.HIGH,
                    block_reason="blocked",
                ),
                explicit_override=True,
            )

    def test_conditionally_approved_no_override_ok(self) -> None:
        r = JoinExecutionRequest(
            validation_report=_validation_report(
                approval_status=JoinApprovalStatus.CONDITIONALLY_APPROVED,
                risk_level=JoinRiskLevel.MEDIUM,
            )
        )
        assert r.explicit_override is False

    def test_override_with_empty_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinExecutionRequest(
                validation_report=_validation_report(
                    approval_status=JoinApprovalStatus.APPROVED,
                    risk_level=JoinRiskLevel.LOW,
                ),
                explicit_override=True,
                override_reason="",
            )


# ---------------------------------------------------------------------------
# JoinExecutionReport
# ---------------------------------------------------------------------------
class TestJoinExecutionReport:
    def test_basic(self) -> None:
        rep = JoinExecutionReport(
            request=JoinExecutionRequest(validation_report=_validation_report()),
            result=_result(),
            status=ExecutionStatus.SUCCEEDED,
        )
        assert rep.status is ExecutionStatus.SUCCEEDED

    def test_with_lineage(self) -> None:
        rep = JoinExecutionReport(
            request=JoinExecutionRequest(validation_report=_validation_report()),
            result=_result(),
            status=ExecutionStatus.SUCCEEDED,
            lineage_id=LineageId("lin-1"),
        )
        assert rep.lineage_id == "lin-1"

    def test_naive_started_at_normalized(self) -> None:
        rep = JoinExecutionReport(
            request=JoinExecutionRequest(validation_report=_validation_report()),
            result=_result(),
            status=ExecutionStatus.SUCCEEDED,
            started_at=datetime(2026, 6, 20, 18, 0, 0),
            finished_at=datetime(2026, 6, 20, 18, 0, 5),
        )
        assert rep.started_at is not None
        assert rep.started_at.tzinfo is timezone.utc
        assert rep.finished_at is not None
        assert rep.finished_at.tzinfo is timezone.utc


# ---------------------------------------------------------------------------
# JoinedDatasetResult
# ---------------------------------------------------------------------------
class TestJoinedDatasetResult:
    def test_basic(self) -> None:
        r = _result()
        assert r.left_dataset_id == "left"
        assert r.right_dataset_id == "right"

    def test_self_join_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinedDatasetResult(
                result_dataset=DatasetHandle(
                    dataset_id="x", dataset_ref="ds-x", name="x"
                ),
                left_dataset_id="x",
                right_dataset_id="x",
            )

    def test_key_columns_lengths_must_match(self) -> None:
        with pytest.raises(ValidationError):
            JoinedDatasetResult(
                result_dataset=DatasetHandle(
                    dataset_id="j", dataset_ref="ds-j", name="j"
                ),
                left_dataset_id="left",
                right_dataset_id="right",
                left_key_columns=("id", "ts"),
                right_key_columns=("cid",),
            )

    def test_duplicate_column_conflicts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinedDatasetResult(
                result_dataset=DatasetHandle(
                    dataset_id="j", dataset_ref="ds-j", name="j"
                ),
                left_dataset_id="left",
                right_dataset_id="right",
                column_conflicts_applied=(
                    ("c", ColumnConflictPolicy.RENAME),
                    ("c", ColumnConflictPolicy.DROP_RIGHT),
                ),
            )

    def test_negative_row_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JoinedDatasetResult(
                result_dataset=DatasetHandle(
                    dataset_id="j", dataset_ref="ds-j", name="j"
                ),
                left_dataset_id="left",
                right_dataset_id="right",
                left_row_count=-1,
            )

    def test_naive_produced_at_normalized(self) -> None:
        r = JoinedDatasetResult(
            result_dataset=DatasetHandle(
                dataset_id="j", dataset_ref="ds-j", name="j"
            ),
            left_dataset_id="left",
            right_dataset_id="right",
            produced_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.produced_at is not None
        assert r.produced_at.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        r = _result()
        assert JoinedDatasetResult.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_joins_contracts_do_not_import_heavy_libs() -> None:
    """Importing the joins contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.joins as joins_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by joins contracts: {leaked}"
