"""Tests for lineage contracts (Build Queue v2.1 Task 21).

Covers:

- ``LineageOperationType`` valid/invalid values.
- ``SourceDatasetRef`` / ``DerivedDatasetRef`` / ``TransformationRef``
  validation, optional fields, and serialization round-trips.
- ``LineageRecord`` invariants: at least one source; ``derived`` is
  required unless ``operation`` is ``PROFILE``; duplicate
  source ``(dataset_id, role)`` pairs are rejected; ``recorded_at`` is
  coerced to UTC.
- ``LineageGraphSnapshot`` invariants: at least one record; lineage
  ids are unique within a snapshot; ``captured_at`` is coerced to UTC.

These tests intentionally avoid importing any heavy compute library so
that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    LineageId,
    Severity,
)
from analytics_platform.contracts.lineage import (
    DerivedDatasetRef,
    LineageGraphSnapshot,
    LineageOperationType,
    LineageRecord,
    SourceDatasetRef,
    TransformationId,
    TransformationRef,
)


# ---------------------------------------------------------------------------
# LineageOperationType
# ---------------------------------------------------------------------------
class TestLineageOperationType:
    def test_known_members(self) -> None:
        assert LineageOperationType.LOAD.value == "load"
        assert LineageOperationType.REGISTER.value == "register"
        assert LineageOperationType.JOIN.value == "join"
        assert LineageOperationType.TRANSFORM.value == "transform"
        assert LineageOperationType.PROFILE.value == "profile"
        assert LineageOperationType.MATERIALIZE.value == "materialize"
        assert LineageOperationType.DERIVE.value == "derive"
        assert LineageOperationType.DROP.value == "drop"

    def test_enum_from_value(self) -> None:
        assert LineageOperationType("load") is LineageOperationType.LOAD
        assert LineageOperationType("join") is LineageOperationType.JOIN

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            LineageOperationType("reindex")  # type: ignore[arg-type]

    def test_is_str_subclass(self) -> None:
        # str-Enum values serialize as plain strings across JSON boundaries.
        assert LineageOperationType.LOAD == "load"


# ---------------------------------------------------------------------------
# Source / derived / transformation references
# ---------------------------------------------------------------------------
def _src(dataset_id: str = "d1", role: str | None = None) -> SourceDatasetRef:
    return SourceDatasetRef(dataset_id=dataset_id, role=role)


def _trans(
    transformation_id: TransformationId = "t1",
    operation: LineageOperationType = LineageOperationType.TRANSFORM,
) -> TransformationRef:
    return TransformationRef(
        transformation_id=transformation_id, operation=operation
    )


def _derived(dataset_id: str = "d2") -> DerivedDatasetRef:
    return DerivedDatasetRef(dataset_id=dataset_id)


class TestSourceDatasetRef:
    def test_minimal(self) -> None:
        s = SourceDatasetRef(dataset_id="d1")
        assert s.dataset_id == "d1"
        assert s.dataset_ref is None
        assert s.fingerprint is None
        assert s.role is None
        assert s.metadata is None

    def test_full(self) -> None:
        s = SourceDatasetRef(
            dataset_id="d1",
            dataset_ref="ds-v1",
            fingerprint="abc",
            role="left",
            metadata={"src": "etl"},
        )
        assert s.dataset_ref == "ds-v1"
        assert s.role == "left"
        assert s.metadata == {"src": "etl"}

    def test_empty_dataset_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDatasetRef(dataset_id="")

    def test_empty_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDatasetRef(dataset_id="d1", role="")

    def test_empty_fingerprint_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDatasetRef(dataset_id="d1", fingerprint="")

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDatasetRef(dataset_id="d1", extra="nope")  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        s = SourceDatasetRef(dataset_id="d1")
        with pytest.raises(ValidationError):
            s.dataset_id = "d2"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        s = SourceDatasetRef(
            dataset_id="d1", dataset_ref="ds-v1", fingerprint="abc", role="left"
        )
        assert SourceDatasetRef.model_validate(s.model_dump(mode="json")) == s


class TestDerivedDatasetRef:
    def test_minimal(self) -> None:
        d = DerivedDatasetRef(dataset_id="d2")
        assert d.dataset_id == "d2"
        assert d.produced_by_lineage_id is None

    def test_with_produced_by(self) -> None:
        d = DerivedDatasetRef(
            dataset_id="d2",
            produced_by_lineage_id="lin-1",
            fingerprint="abc",
        )
        assert d.produced_by_lineage_id == "lin-1"

    def test_round_trip(self) -> None:
        d = DerivedDatasetRef(
            dataset_id="d2",
            produced_by_lineage_id="lin-1",
            dataset_ref="ds-v2",
        )
        assert DerivedDatasetRef.model_validate(d.model_dump(mode="json")) == d


class TestTransformationRef:
    def test_minimal(self) -> None:
        t = TransformationRef(
            transformation_id="t1", operation=LineageOperationType.LOAD
        )
        assert t.transformation_id == "t1"
        assert t.operation is LineageOperationType.LOAD
        assert t.code is None
        assert t.stage_id is None
        assert t.run_id is None

    def test_full(self) -> None:
        t = TransformationRef(
            transformation_id="t1",
            operation=LineageOperationType.JOIN,
            code="join.inner.on=customer_id",
            stage_id="stage-join",
            run_id="run-1",
            parameters_fingerprint="ph-1",
            metadata={"k": "v"},
        )
        assert t.code == "join.inner.on=customer_id"
        assert t.stage_id == "stage-1" or t.stage_id == "stage-join"
        assert t.parameters_fingerprint == "ph-1"

    def test_empty_transformation_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TransformationRef(
                transformation_id="", operation=LineageOperationType.LOAD
            )

    def test_round_trip(self) -> None:
        t = TransformationRef(
            transformation_id="t1",
            operation=LineageOperationType.JOIN,
            code="join.inner",
            stage_id="stage-join",
            run_id="run-1",
        )
        assert TransformationRef.model_validate(t.model_dump(mode="json")) == t


# ---------------------------------------------------------------------------
# LineageRecord
# ---------------------------------------------------------------------------
def _ok_record(
    *,
    operation: LineageOperationType = LineageOperationType.TRANSFORM,
    sources: tuple[SourceDatasetRef, ...] = (_src("d1"),),
    transformation: TransformationRef | None = None,
    derived: DerivedDatasetRef | None = None,
) -> LineageRecord:
    # ``operation`` defaults to TRANSFORM, which requires a non-None
    # ``derived`` per the LineageRecord validator. Default the derived
    # ref when the caller hasn't explicitly passed one.
    if derived is None and operation is not LineageOperationType.PROFILE:
        derived = _derived("d2")
    return LineageRecord(
        lineage_id="lin-1",
        operation=operation,
        sources=sources,
        transformation=transformation or _trans(),
        derived=derived,
    )


class TestLineageRecord:
    def test_minimal_with_derived(self) -> None:
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.TRANSFORM,
            sources=(_src("d1"),),
            transformation=_trans(),
            derived=_derived("d2"),
        )
        assert rec.lineage_id == "lin-1"
        assert rec.derived is not None
        assert rec.derived.dataset_id == "d2"

    def test_requires_at_least_one_source(self) -> None:
        with pytest.raises(ValidationError):
            LineageRecord(
                lineage_id="lin-1",
                operation=LineageOperationType.TRANSFORM,
                sources=(),
                transformation=_trans(),
                derived=_derived("d2"),
            )

    def test_derived_required_for_non_profile_operations(self) -> None:
        for op in (
            LineageOperationType.LOAD,
            LineageOperationType.REGISTER,
            LineageOperationType.JOIN,
            LineageOperationType.TRANSFORM,
            LineageOperationType.MATERIALIZE,
            LineageOperationType.DERIVE,
            LineageOperationType.DROP,
        ):
            with pytest.raises(ValidationError):
                LineageRecord(
                    lineage_id="lin-1",
                    operation=op,
                    sources=(_src("d1"),),
                    transformation=_trans(operation=op),
                    derived=None,
                )

    def test_profile_operation_may_omit_derived(self) -> None:
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.PROFILE,
            sources=(_src("d1"),),
            transformation=_trans(operation=LineageOperationType.PROFILE),
            derived=None,
        )
        assert rec.derived is None
        assert rec.operation is LineageOperationType.PROFILE

    def test_duplicate_source_dataset_id_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LineageRecord(
                lineage_id="lin-1",
                operation=LineageOperationType.JOIN,
                sources=(
                    _src("d1", role="left"),
                    _src("d1", role="left"),  # duplicate
                ),
                transformation=_trans(operation=LineageOperationType.JOIN),
                derived=_derived("d2"),
            )

    def test_same_dataset_id_different_role_ok(self) -> None:
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.JOIN,
            sources=(
                _src("d1", role="left"),
                _src("d1", role="right"),
            ),
            transformation=_trans(operation=LineageOperationType.JOIN),
            derived=_derived("d2"),
        )
        assert len(rec.sources) == 2

    def test_same_dataset_id_no_role_treated_as_duplicate(self) -> None:
        with pytest.raises(ValidationError):
            LineageRecord(
                lineage_id="lin-1",
                operation=LineageOperationType.TRANSFORM,
                sources=(_src("d1"), _src("d1")),
                transformation=_trans(),
                derived=_derived("d2"),
            )

    def test_naive_recorded_at_normalized(self) -> None:
        # Naive datetimes are coerced to UTC at validation time.
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.TRANSFORM,
            sources=(_src("d1"),),
            transformation=_trans(),
            derived=_derived("d2"),
            recorded_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert rec.recorded_at is not None
        assert rec.recorded_at.tzinfo is timezone.utc

        # ``recorded_at`` defaults to None when not provided.
        rec_default = _ok_record()
        assert rec_default.recorded_at is None

    def test_aware_recorded_at_preserved(self) -> None:
        aware = datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc)
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.TRANSFORM,
            sources=(_src("d1"),),
            transformation=_trans(),
            derived=_derived("d2"),
            recorded_at=aware,
        )
        assert rec.recorded_at == aware

    def test_with_issues_and_warnings(self) -> None:
        rec = LineageRecord(
            lineage_id="lin-1",
            operation=LineageOperationType.TRANSFORM,
            sources=(_src("d1"),),
            transformation=_trans(),
            derived=_derived("d2"),
            issues=(Issue(code="X", severity=Severity.WARNING, message="m"),),
        )
        assert len(rec.issues) == 1

    def test_round_trip(self) -> None:
        rec = _ok_record()
        restored = LineageRecord.model_validate(rec.model_dump(mode="json"))
        assert restored == rec
        assert restored.derived is not None


# ---------------------------------------------------------------------------
# LineageGraphSnapshot
# ---------------------------------------------------------------------------
class TestLineageGraphSnapshot:
    def _ok_snapshot(
        self,
        *,
        records: tuple[LineageRecord, ...] | None = None,
        run_id: str = "run-1",
    ) -> LineageGraphSnapshot:
        if records is None:
            records = (
                LineageRecord(
                    lineage_id="lin-1",
                    operation=LineageOperationType.TRANSFORM,
                    sources=(_src("d1"),),
                    transformation=_trans(),
                    derived=_derived("d2"),
                ),
            )
        return LineageGraphSnapshot(
            snapshot_id="snap-1",
            run_id=run_id,
            records=records,
        )

    def test_minimal(self) -> None:
        snap = self._ok_snapshot()
        assert snap.snapshot_id == "snap-1"
        assert snap.run_id == "run-1"
        assert len(snap.records) == 1
        assert snap.root_dataset_ids == ()
        assert snap.stage_ids == ()

    def test_full(self) -> None:
        snap = LineageGraphSnapshot(
            snapshot_id="snap-1",
            run_id="run-1",
            records=(
                LineageRecord(
                    lineage_id="lin-1",
                    operation=LineageOperationType.TRANSFORM,
                    sources=(_src("d1"),),
                    transformation=_trans(),
                    derived=_derived("d2"),
                ),
            ),
            root_dataset_ids=("d1",),
            stage_ids=("stage-load",),
            captured_at=datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc),
            issues=(
                Issue(code="X", severity=Severity.WARNING, message="m"),
            ),
            metadata={"k": "v"},
        )
        assert snap.root_dataset_ids == ("d1",)
        assert snap.stage_ids == ("stage-load",)
        assert len(snap.issues) == 1

    def test_requires_at_least_one_record(self) -> None:
        with pytest.raises(ValidationError):
            LineageGraphSnapshot(
                snapshot_id="snap-1",
                run_id="run-1",
                records=(),
            )

    def test_duplicate_lineage_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._ok_snapshot(
                records=(
                    LineageRecord(
                        lineage_id="lin-1",
                        operation=LineageOperationType.TRANSFORM,
                        sources=(_src("d1"),),
                        transformation=_trans(),
                        derived=_derived("d2"),
                    ),
                    LineageRecord(
                        lineage_id="lin-1",  # duplicate
                        operation=LineageOperationType.TRANSFORM,
                        sources=(_src("d3"),),
                        transformation=_trans(transformation_id="t2"),
                        derived=_derived("d4"),
                    ),
                ),
            )

    def test_naive_captured_at_normalized(self) -> None:
        snap = LineageGraphSnapshot(
            snapshot_id="snap-1",
            run_id="run-1",
            records=(
                LineageRecord(
                    lineage_id="lin-1",
                    operation=LineageOperationType.TRANSFORM,
                    sources=(_src("d1"),),
                    transformation=_trans(),
                    derived=_derived("d2"),
                ),
            ),
            captured_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert snap.captured_at is not None
        assert snap.captured_at.tzinfo is timezone.utc

    def test_aware_captured_at_preserved(self) -> None:
        aware = datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc)
        snap = LineageGraphSnapshot(
            snapshot_id="snap-1",
            run_id="run-1",
            records=(
                LineageRecord(
                    lineage_id="lin-1",
                    operation=LineageOperationType.TRANSFORM,
                    sources=(_src("d1"),),
                    transformation=_trans(),
                    derived=_derived("d2"),
                ),
            ),
            captured_at=aware,
        )
        assert snap.captured_at == aware

    def test_round_trip(self) -> None:
        snap = self._ok_snapshot()
        restored = LineageGraphSnapshot.model_validate(snap.model_dump(mode="json"))
        assert restored == snap


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_lineage_contracts_do_not_import_heavy_libs() -> None:
    """Importing the lineage contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.lineage as lineage_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by lineage contracts: {leaked}"
