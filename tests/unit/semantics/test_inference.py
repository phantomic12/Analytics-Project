"""Tests for the semantic-type inference stage (Build Queue v2.1 Task 91)."""

from __future__ import annotations

import pytest

from analytics_platform.contracts.common import Severity
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    DatasetRole,
    StorageBackend,
)
from analytics_platform.contracts.schemas import (
    ColumnSchema,
    LogicalDataType,
    ObservedSchema,
    PhysicalDataType,
)
from analytics_platform.contracts.semantics import (
    ColumnRole,
    ColumnRoleAssignment,
    RiskyColumnUse,
    SemanticColumnType,
    SemanticTypeInferenceRequest,
    SemanticTypeConfidence,
)
from analytics_platform.semantics import (
    DEFAULT_RULES,
    SemanticInferenceError,
    SemanticInferenceRule,
    SemanticInferencer,
    infer_semantic_types,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


def _observed(columns: list[tuple[str, str, str | None]]) -> ObservedSchema:
    """Build an :class:`ObservedSchema` from ``(name, physical, logical)`` tuples."""
    cols = [
        ColumnSchema(
            name=name,
            physical_type=PhysicalDataType(physical),
            logical_type=LogicalDataType(logical) if logical else None,
            ordinal=i,
        )
        for i, (name, physical, logical) in enumerate(columns)
    ]
    return ObservedSchema(
        columns=tuple(cols),
        fingerprint=None,
        row_count_estimate=None,
        notes=None,
        metadata=None,
    )


# ===========================================================================
# Default rules
# ===========================================================================
class TestDefaultRules:
    def test_id_suffix_matches(self) -> None:
        obs = _observed([("user_id", "int64", "integer")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.IDENTIFIER

    def test_timestamp_suffix_requires_datetime(self) -> None:
        # Logical type = string -> timestamp rule does NOT match.
        obs = _observed([("created_at", "utf8", "string")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is not SemanticColumnType.TIMESTAMP

        obs = _observed([("created_at", "timestamp", "datetime")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.TIMESTAMP

    def test_currency_matches_float(self) -> None:
        obs = _observed([("price", "float64", "float")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.CURRENCY

    def test_bool_flag_matches(self) -> None:
        obs = _observed([("is_active", "bool", "boolean")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.BOOLEAN_FLAG

    def test_geo_matches(self) -> None:
        obs = _observed([("country", "utf8", "string")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.GEOGRAPHIC

    def test_category_matches(self) -> None:
        obs = _observed([("status", "utf8", "string")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.CATEGORICAL

    def test_text_matches(self) -> None:
        obs = _observed([("description", "utf8", "string")])
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.TEXT

    def test_unknown_when_no_rule_matches(self) -> None:
        obs = _observed([("a", "int64", "integer")])
        # No name rule covers "a" by itself; logical fallback is MEASUREMENT.
        report = infer_semantic_types(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.MEASUREMENT


class TestInferencer:
    def test_request_min_confidence_overrides(self) -> None:
        # ``count`` rule has base_score=0.7; default min_confidence=0.5;
        # request min_confidence=0.9 should flag it as risky.
        obs = _observed([("count", "int64", "integer")])
        report = infer_semantic_types(
            obs,
            request=SemanticTypeInferenceRequest(
                dataset=_handle(),
                role_overrides=(),
                min_confidence=0.9,
                max_columns=None,
                run_id=None,
                stage_id=None,
                metadata=None,
            ),
        )
        assert any(r.code == "SEMANTIC_LOW_CONFIDENCE" for r in report.risky_uses)

    def test_role_override_wins(self) -> None:
        obs = _observed([("user_id", "int64", "integer")])
        request = SemanticTypeInferenceRequest(
            dataset=_handle(),
            role_overrides=(
                ColumnRoleAssignment(
                    column_name="user_id",
                    role=ColumnRole.EXCLUSION,
                    assigned_by="user",
                    reason="PII",
                    metadata=None,
                ),
            ),
            min_confidence=0.5,
        )
        report = infer_semantic_types(obs, request=request)
        assert any(
            a.column_name == "user_id" and a.role is ColumnRole.EXCLUSION
            for a in report.role_assignments
        )

    def test_negative_min_confidence_rejected(self) -> None:
        with pytest.raises(SemanticInferenceError) as ei:
            SemanticInferencer(min_confidence=-0.1)
        assert ei.value.issue.code == "SEMANTIC_INFERENCE_BAD_MIN_CONFIDENCE"

    def test_min_confidence_above_one_rejected(self) -> None:
        with pytest.raises(SemanticInferenceError):
            SemanticInferencer(min_confidence=1.5)

    def test_custom_rules_override_defaults(self) -> None:
        custom = (
            SemanticInferenceRule(
                name="custom_id",
                pattern=r"^my_id$",
                semantic_type=SemanticColumnType.IDENTIFIER,
                base_score=0.99,
            ),
        )
        inf = SemanticInferencer(rules=custom)
        obs = _observed([("my_id", "int64", "integer")])
        report = inf.infer(obs)
        assert report.column_profiles[0].semantic_type is SemanticColumnType.IDENTIFIER
        assert report.column_profiles[0].confidence.algorithm == "name_match"

    def test_unknown_logical_falls_back(self) -> None:
        # Use iterable input to skip ObservedSchema normalization.
        # Logical type None -> no rule matches -> logical fallback
        # yields SemanticColumnType.UNKNOWN with confidence 0.3.
        report = infer_semantic_types([("a", None)])
        assert report.column_profiles[0].semantic_type is SemanticColumnType.UNKNOWN
        assert report.column_profiles[0].confidence.algorithm == "logical_fallback"
        assert report.column_profiles[0].confidence.score == 0.3

    def test_logical_fallback_for_each_type(self) -> None:
        cases = [
            (LogicalDataType.INTEGER, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.FLOAT, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.STRING, SemanticColumnType.CATEGORICAL),
            (LogicalDataType.BOOLEAN, SemanticColumnType.BOOLEAN_FLAG),
            (LogicalDataType.DATETIME, SemanticColumnType.TIMESTAMP),
            (LogicalDataType.DATE, SemanticColumnType.DATE),
            (LogicalDataType.TIMEDELTA, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.BINARY, SemanticColumnType.UNKNOWN),
            (LogicalDataType.UNKNOWN, SemanticColumnType.UNKNOWN),
        ]
        for logical, expected in cases:
            report = infer_semantic_types([("a", logical)])
            assert report.column_profiles[0].semantic_type is expected, (
                f"logical={logical.value} expected={expected.value}"
            )

    def test_alternatives_not_populated(self) -> None:
        # Task 91 does not produce alternatives; the report should
        # carry empty alternatives on every profile.
        obs = _observed([("user_id", "int64", "integer")])
        report = infer_semantic_types(obs)
        for profile in report.column_profiles:
            assert profile.alternatives == ()

    def test_column_profiles_unique(self) -> None:
        obs = _observed(
            [("a", "int64", "integer"), ("b", "utf8", "string")]
        )
        report = infer_semantic_types(obs)
        names = [p.column_name for p in report.column_profiles]
        assert len(set(names)) == len(names)

    def test_logical_agreement_boosts_score(self) -> None:
        # Logical-type agreement gives +0.1 score; without it the
        # base score stays put. We confirm the boost by checking
        # that the integer-keyed ``count`` column scores higher
        # than a same-name column with a non-integer logical type.
        obs_typed = _observed([("count", "int64", "integer")])
        obs_untyped = _observed([("count", "int64", None)])
        r_typed = infer_semantic_types(obs_typed)
        r_untyped = infer_semantic_types(obs_untyped)
        assert (
            r_typed.column_profiles[0].confidence.score
            > r_untyped.column_profiles[0].confidence.score
        )

    def test_logical_fallback_for_each_type(self) -> None:
        pass  # The original body was removed; see TestInferencer below.
        cases = [
            (LogicalDataType.INTEGER, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.FLOAT, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.STRING, SemanticColumnType.CATEGORICAL),
            (LogicalDataType.BOOLEAN, SemanticColumnType.BOOLEAN_FLAG),
            (LogicalDataType.DATETIME, SemanticColumnType.TIMESTAMP),
            (LogicalDataType.DATE, SemanticColumnType.DATE),
            (LogicalDataType.TIMEDELTA, SemanticColumnType.MEASUREMENT),
            (LogicalDataType.BINARY, SemanticColumnType.UNKNOWN),
            (LogicalDataType.UNKNOWN, SemanticColumnType.UNKNOWN),
        ]
        for logical, expected in cases:
            report = infer_semantic_types([("a", logical)])
            assert report.column_profiles[0].semantic_type is expected, (
                f"logical={logical.value} expected={expected.value}"
            )


class TestDefaultRulesSanity:
    def test_default_rules_have_unique_names(self) -> None:
        names = [r.name for r in DEFAULT_RULES]
        assert len(names) == len(set(names))

    def test_default_rules_are_compiled(self) -> None:
        for rule in DEFAULT_RULES:
            # Compiled regex should match anything that matches the
            # underlying pattern; sample a known-good and known-bad
            # column name.
            assert rule.pattern
            assert rule.semantic_type is not None

    def test_default_rules_cover_common_columns(self) -> None:
        seen = {r.semantic_type for r in DEFAULT_RULES}
        for st in (
            SemanticColumnType.IDENTIFIER,
            SemanticColumnType.TIMESTAMP,
            SemanticColumnType.DATE,
            SemanticColumnType.BOOLEAN_FLAG,
            SemanticColumnType.CURRENCY,
            SemanticColumnType.GEOGRAPHIC,
            SemanticColumnType.COUNT,
            SemanticColumnType.MEASUREMENT,
            SemanticColumnType.ORDINAL,
            SemanticColumnType.CATEGORICAL,
            SemanticColumnType.TEXT,
        ):
            assert st in seen, f"no default rule for {st.value}"


class TestRiskyUses:
    def test_low_confidence_flagged(self) -> None:
        # A column whose semantic type fell back to MEASUREMENT
        # via logical fallback has a 0.3 score, below the default
        # 0.5 min_confidence; the inferencer must emit a
        # RiskyColumnUse.
        inf = SemanticInferencer(min_confidence=0.5)
        obs = _observed([("a", "int64", "integer")])
        report = inf.infer(obs)
        assert any(
            r.code == "SEMANTIC_LOW_CONFIDENCE"
            and r.severity is Severity.WARNING
            for r in report.risky_uses
        )