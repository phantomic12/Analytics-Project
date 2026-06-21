"""Tests for semantic column typing contracts (Build Queue v2.1 Task 23).

Covers:

- ``SemanticColumnType`` / ``ColumnRole`` valid/invalid values.
- ``SemanticTypeConfidence`` bounds and serialization.
- ``ColumnRoleAssignment`` instantiation and serialization.
- ``SemanticColumnProfile`` invariants (alternatives do not repeat the
  primary type).
- ``RiskyColumnUse`` instantiation and serialization.
- ``SemanticTypeInferenceRequest`` invariants (unique role-override
  column names; ``min_confidence`` bounds).
- ``SemanticTypeInferenceReport`` invariants (unique column-profile and
  role-assignment column names; at least one profile).

These tests intentionally avoid importing any heavy compute library so
that they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import LogicalDataType
from analytics_platform.contracts.semantics import (
    ColumnRole,
    ColumnRoleAssignment,
    RiskyColumnUse,
    SemanticColumnProfile,
    SemanticColumnType,
    SemanticTypeConfidence,
    SemanticTypeInferenceReport,
    SemanticTypeInferenceRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle(name: str = "orders") -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name=name)


def _profile(
    column_name: str = "id",
    semantic_type: SemanticColumnType = SemanticColumnType.IDENTIFIER,
    score: float = 0.9,
) -> SemanticColumnProfile:
    return SemanticColumnProfile(
        column_name=column_name,
        semantic_type=semantic_type,
        confidence=SemanticTypeConfidence(score=score, algorithm="rule_based"),
        logical_type=(
            LogicalDataType.STRING
            if semantic_type is SemanticColumnType.IDENTIFIER
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestSemanticColumnType:
    def test_known_members(self) -> None:
        assert SemanticColumnType.IDENTIFIER.value == "identifier"
        assert SemanticColumnType.CATEGORICAL.value == "categorical"
        assert SemanticColumnType.MEASUREMENT.value == "measurement"
        assert SemanticColumnType.TIMESTAMP.value == "timestamp"
        assert SemanticColumnType.UNKNOWN.value == "unknown"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            SemanticColumnType("email")  # type: ignore[arg-type]


class TestColumnRole:
    def test_known_members(self) -> None:
        assert ColumnRole.TARGET.value == "target"
        assert ColumnRole.FEATURE.value == "feature"
        assert ColumnRole.EXCLUSION.value == "exclusion"
        assert ColumnRole.GROUP_KEY.value == "group_key"
        assert ColumnRole.WEIGHT.value == "weight"
        assert ColumnRole.TIME_INDEX.value == "time_index"
        assert ColumnRole.NONE.value == "none"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ColumnRole("primary_key")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SemanticTypeConfidence
# ---------------------------------------------------------------------------
class TestSemanticTypeConfidence:
    def test_minimal(self) -> None:
        c = SemanticTypeConfidence(score=0.5)
        assert c.score == 0.5
        assert c.algorithm is None
        assert c.evidence_count is None

    def test_full(self) -> None:
        c = SemanticTypeConfidence(
            score=0.9, algorithm="name_match", evidence_count=3, notes="ok"
        )
        assert c.algorithm == "name_match"
        assert c.evidence_count == 3

    def test_score_bounds(self) -> None:
        # Bounded inclusive.
        SemanticTypeConfidence(score=0.0)
        SemanticTypeConfidence(score=1.0)

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeConfidence(score=1.5)

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeConfidence(score=-0.1)

    def test_negative_evidence_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeConfidence(score=0.5, evidence_count=-1)

    def test_round_trip(self) -> None:
        c = SemanticTypeConfidence(score=0.7, algorithm="a", evidence_count=2)
        assert SemanticTypeConfidence.model_validate(c.model_dump(mode="json")) == c


# ---------------------------------------------------------------------------
# ColumnRoleAssignment
# ---------------------------------------------------------------------------
class TestColumnRoleAssignment:
    def test_minimal(self) -> None:
        a = ColumnRoleAssignment(column_name="amount", role=ColumnRole.FEATURE)
        assert a.column_name == "amount"
        assert a.role is ColumnRole.FEATURE
        assert a.assigned_by is None
        assert a.assigned_at_confidence is None

    def test_full(self) -> None:
        a = ColumnRoleAssignment(
            column_name="amount",
            role=ColumnRole.TARGET,
            assigned_by="user",
            assigned_at_confidence=SemanticTypeConfidence(score=1.0),
            reason="user-declared",
        )
        assert a.assigned_by == "user"
        assert a.assigned_at_confidence is not None

    def test_empty_column_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColumnRoleAssignment(column_name="", role=ColumnRole.FEATURE)

    def test_round_trip(self) -> None:
        a = ColumnRoleAssignment(column_name="x", role=ColumnRole.FEATURE)
        assert ColumnRoleAssignment.model_validate(a.model_dump(mode="json")) == a


# ---------------------------------------------------------------------------
# SemanticColumnProfile
# ---------------------------------------------------------------------------
class TestSemanticColumnProfile:
    def test_minimal(self) -> None:
        p = _profile()
        assert p.column_name == "id"
        assert p.semantic_type is SemanticColumnType.IDENTIFIER
        assert p.confidence.score == 0.9
        assert p.alternatives == ()

    def test_alternatives(self) -> None:
        p = SemanticColumnProfile(
            column_name="amount",
            semantic_type=SemanticColumnType.MEASUREMENT,
            confidence=SemanticTypeConfidence(score=0.7),
            alternatives=(
                (
                    SemanticColumnType.CURRENCY,
                    SemanticTypeConfidence(score=0.5),
                ),
            ),
        )
        assert len(p.alternatives) == 1

    def test_alternative_matches_primary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticColumnProfile(
                column_name="amount",
                semantic_type=SemanticColumnType.MEASUREMENT,
                confidence=SemanticTypeConfidence(score=0.7),
                alternatives=(
                    (
                        SemanticColumnType.MEASUREMENT,
                        SemanticTypeConfidence(score=0.5),
                    ),
                ),
            )

    def test_empty_column_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticColumnProfile(
                column_name="",
                semantic_type=SemanticColumnType.IDENTIFIER,
                confidence=SemanticTypeConfidence(score=0.5),
            )

    def test_round_trip(self) -> None:
        p = _profile()
        assert SemanticColumnProfile.model_validate(p.model_dump(mode="json")) == p


# ---------------------------------------------------------------------------
# RiskyColumnUse
# ---------------------------------------------------------------------------
class TestRiskyColumnUse:
    def test_minimal(self) -> None:
        r = RiskyColumnUse(
            column_name="id",
            inferred_semantic_type=SemanticColumnType.IDENTIFIER,
            actual_use="used as a feature",
        )
        assert r.severity is Severity.WARNING
        assert r.code is None

    def test_full(self) -> None:
        r = RiskyColumnUse(
            column_name="id",
            inferred_semantic_type=SemanticColumnType.IDENTIFIER,
            inferred_role=ColumnRole.FEATURE,
            actual_use="used as a regression target",
            severity=Severity.ERROR,
            code="RISKY_ID_AS_TARGET",
            message="identifiers must not be used as targets",
            run_id="r1",
            stage_id="stage-semantics",
        )
        assert r.severity is Severity.ERROR

    def test_empty_actual_use_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RiskyColumnUse(
                column_name="id",
                inferred_semantic_type=SemanticColumnType.IDENTIFIER,
                actual_use="",
            )

    def test_round_trip(self) -> None:
        r = RiskyColumnUse(
            column_name="id",
            inferred_semantic_type=SemanticColumnType.IDENTIFIER,
            actual_use="used as a feature",
        )
        assert RiskyColumnUse.model_validate(r.model_dump(mode="json")) == r


# ---------------------------------------------------------------------------
# SemanticTypeInferenceRequest
# ---------------------------------------------------------------------------
class TestSemanticTypeInferenceRequest:
    def test_minimal(self) -> None:
        r = SemanticTypeInferenceRequest(dataset=_handle())
        assert r.role_overrides == ()
        assert r.min_confidence == 0.5
        assert r.max_columns is None

    def test_full(self) -> None:
        r = SemanticTypeInferenceRequest(
            dataset=_handle(),
            role_overrides=(
                ColumnRoleAssignment(
                    column_name="amount", role=ColumnRole.TARGET
                ),
            ),
            min_confidence=0.7,
            max_columns=50,
        )
        assert len(r.role_overrides) == 1
        assert r.min_confidence == 0.7

    def test_min_confidence_bounds(self) -> None:
        SemanticTypeInferenceRequest(dataset=_handle(), min_confidence=0.0)
        SemanticTypeInferenceRequest(dataset=_handle(), min_confidence=1.0)

    def test_min_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceRequest(
                dataset=_handle(), min_confidence=1.5
            )

    def test_negative_max_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceRequest(dataset=_handle(), max_columns=-1)

    def test_duplicate_role_override_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceRequest(
                dataset=_handle(),
                role_overrides=(
                    ColumnRoleAssignment(
                        column_name="x", role=ColumnRole.FEATURE
                    ),
                    ColumnRoleAssignment(
                        column_name="x", role=ColumnRole.TARGET
                    ),
                ),
            )


# ---------------------------------------------------------------------------
# SemanticTypeInferenceReport
# ---------------------------------------------------------------------------
class TestSemanticTypeInferenceReport:
    def test_minimal(self) -> None:
        rep = SemanticTypeInferenceReport(
            dataset=_handle(), column_profiles=(_profile(),)
        )
        assert rep.role_assignments == ()
        assert rep.risky_uses == ()
        assert rep.issues == ()
        assert rep.warnings == ()

    def test_full(self) -> None:
        rep = SemanticTypeInferenceReport(
            dataset=_handle(),
            column_profiles=(
                _profile("id", SemanticColumnType.IDENTIFIER),
                _profile(
                    "amount", SemanticColumnType.MEASUREMENT, score=0.8
                ),
            ),
            role_assignments=(
                ColumnRoleAssignment(
                    column_name="amount", role=ColumnRole.TARGET
                ),
            ),
            risky_uses=(
                RiskyColumnUse(
                    column_name="id",
                    inferred_semantic_type=SemanticColumnType.IDENTIFIER,
                    actual_use="used as a feature",
                ),
            ),
            issues=(
                Issue(
                    code="X", severity=Severity.WARNING, message="w"
                ),
            ),
            warnings=(
                WarningRecord(code="W", message="w"),
            ),
        )
        assert len(rep.column_profiles) == 2
        assert len(rep.role_assignments) == 1
        assert len(rep.risky_uses) == 1

    def test_requires_at_least_one_profile(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceReport(
                dataset=_handle(), column_profiles=()
            )

    def test_duplicate_profile_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceReport(
                dataset=_handle(),
                column_profiles=(
                    _profile("id"),
                    _profile("id", SemanticColumnType.MEASUREMENT),
                ),
            )

    def test_duplicate_role_assignment_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticTypeInferenceReport(
                dataset=_handle(),
                column_profiles=(_profile("id"),),
                role_assignments=(
                    ColumnRoleAssignment(
                        column_name="id", role=ColumnRole.FEATURE
                    ),
                    ColumnRoleAssignment(
                        column_name="id", role=ColumnRole.TARGET
                    ),
                ),
            )

    def test_round_trip(self) -> None:
        rep = SemanticTypeInferenceReport(
            dataset=_handle(), column_profiles=(_profile(),)
        )
        assert SemanticTypeInferenceReport.model_validate(
            rep.model_dump(mode="json")
        ) == rep


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_semantics_contracts_do_not_import_heavy_libs() -> None:
    """Importing the semantics contracts module must not pull heavy libs.

    Mirrors the per-module guards on the other contract families and
    protects the contract-first discipline spelled out in
    ``docs/contracts/contracts-index-v1.1.md``.
    """
    import sys

    import analytics_platform.contracts.semantics as semantics_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, (
        f"heavy libs imported by semantics contracts: {leaked}"
    )
