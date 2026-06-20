"""Tests for common shared contracts (Build Queue v2.1 Task 11).

Covers:
- valid instantiation of the key types/models,
- invalid enum / model validation,
- serialization round-trips for ``Issue``, ``WarningRecord``, ``ArtifactRef``,
  and ``StageResult``.

These tests intentionally avoid importing any heavy compute library so that
they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    ArtifactRef,
    ExecutionStatus,
    Issue,
    MetricValue,
    RunId,
    Severity,
    StageResult,
    WarningRecord,
)


# ---------------------------------------------------------------------------
# Severity / ExecutionStatus enums
# ---------------------------------------------------------------------------
class TestSeverity:
    def test_known_members(self) -> None:
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"

    def test_enum_from_value(self) -> None:
        assert Severity("error") is Severity.ERROR

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            Severity("catastrophic")  # type: ignore[arg-type]


class TestExecutionStatus:
    def test_known_members(self) -> None:
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.SUCCEEDED.value == "succeeded"
        assert ExecutionStatus.FAILED.value == "failed"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExecutionStatus("done")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------
class TestIssue:
    def test_valid_minimal(self) -> None:
        issue = Issue(code="SCHEMA_MISMATCH", severity=Severity.ERROR, message="bad column")
        assert issue.code == "SCHEMA_MISMATCH"
        assert issue.severity is Severity.ERROR
        assert issue.run_id is None
        assert issue.context is None

    def test_valid_with_locators_and_context(self) -> None:
        issue = Issue(
            code="ROW_COUNT_DRIFT",
            severity=Severity.WARNING,
            message="row count changed",
            run_id="run-1",
            stage_id="stage-load",
            dataset_id="ds-v1",
            context={"expected": "100", "actual": "98"},
        )
        assert issue.run_id == "run-1"
        assert issue.context == {"expected": "100", "actual": "98"}

    def test_severity_string_coerced(self) -> None:
        issue = Issue(code="C1", severity="critical", message="m")  # type: ignore[arg-type]
        assert issue.severity is Severity.CRITICAL

    def test_invalid_severity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Issue(code="C1", severity="fatal", message="m")  # type: ignore[arg-type]

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Issue(code="", severity=Severity.INFO, message="m")

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Issue(code="C1", severity=Severity.INFO, message="")

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Issue(code="C1", severity=Severity.INFO, message="m", extra="x")  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        issue = Issue(code="C1", severity=Severity.INFO, message="m")
        with pytest.raises(ValidationError):
            issue.code = "C2"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        issue = Issue(
            code="ROUND_TRIP",
            severity=Severity.ERROR,
            message="rt",
            run_id="r1",
            stage_id="s1",
            dataset_id="d1",
            context={"k": "v"},
        )
        data = issue.model_dump(mode="json")
        restored = Issue.model_validate(data)
        assert restored == issue


# ---------------------------------------------------------------------------
# WarningRecord
# ---------------------------------------------------------------------------
class TestWarningRecord:
    def test_valid(self) -> None:
        w = WarningRecord(code="SLOW_QUERY", message="query slow", run_id="r1")
        assert w.code == "SLOW_QUERY"
        assert w.run_id == "r1"

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WarningRecord(code="C1", message="")

    def test_round_trip(self) -> None:
        w = WarningRecord(
            code="WARN_RT",
            message="rt",
            run_id="r1",
            stage_id="s1",
            dataset_id="d1",
            context={"a": "b"},
        )
        restored = WarningRecord.model_validate(w.model_dump(mode="json"))
        assert restored == w


# ---------------------------------------------------------------------------
# MetricValue
# ---------------------------------------------------------------------------
class TestMetricValue:
    def test_valid_with_int_coerced_to_float(self) -> None:
        m = MetricValue(name="rows", value=100)  # type: ignore[arg-type]
        assert m.value == 100.0
        assert isinstance(m.value, float)

    def test_unit_and_tags_optional(self) -> None:
        m = MetricValue(name="latency", value=1.5, unit="seconds", tags={"phase": "load"})
        assert m.unit == "seconds"
        assert m.tags == {"phase": "load"}

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MetricValue(name="", value=1.0)


# ---------------------------------------------------------------------------
# ArtifactRef
# ---------------------------------------------------------------------------
class TestArtifactRef:
    def test_valid(self) -> None:
        ref = ArtifactRef(artifact_id="art-1", kind="dataset", uri="file:///tmp/a.parquet")
        assert ref.artifact_id == "art-1"
        assert ref.kind == "dataset"
        assert ref.uri.startswith("file://")

    def test_empty_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactRef(artifact_id="a1", kind="dataset", uri="")

    def test_empty_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactRef(artifact_id="a1", kind="", uri="file://x")

    def test_round_trip(self) -> None:
        ref = ArtifactRef(
            artifact_id="art-rt",
            kind="report",
            uri="s3://bucket/key.html",
            run_id="r1",
            stage_id="s1",
            metadata={"fmt": "html"},
        )
        restored = ArtifactRef.model_validate(ref.model_dump(mode="json"))
        assert restored == ref


# ---------------------------------------------------------------------------
# StageResult
# ---------------------------------------------------------------------------
class TestStageResult:
    def _sample(self) -> StageResult:
        return StageResult(
            stage_id="stage-1",
            status=ExecutionStatus.SUCCEEDED,
            run_id="run-1",
            message="ok",
            issues=(Issue(code="I1", severity=Severity.WARNING, message="w"),),
            warnings=(WarningRecord(code="W1", message="w"),),
            metrics=(MetricValue(name="rows", value=10.0),),
            artifacts=(
                ArtifactRef(artifact_id="a1", kind="dataset", uri="file:///x"),
            ),
        )

    def test_valid_with_nested_collections(self) -> None:
        sr = self._sample()
        assert sr.status is ExecutionStatus.SUCCEEDED
        assert len(sr.issues) == 1
        assert sr.issues[0].severity is Severity.WARNING
        assert len(sr.metrics) == 1
        assert sr.metrics[0].value == 10.0
        assert sr.artifacts[0].artifact_id == "a1"

    def test_defaults_empty_tuples(self) -> None:
        sr = StageResult(stage_id="s", status=ExecutionStatus.PENDING)
        assert sr.issues == ()
        assert sr.warnings == ()
        assert sr.metrics == ()
        assert sr.artifacts == ()
        assert sr.message is None

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StageResult(stage_id="s", status="done")  # type: ignore[arg-type]

    def test_empty_stage_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StageResult(stage_id="", status=ExecutionStatus.PENDING)

    def test_frozen(self) -> None:
        sr = self._sample()
        with pytest.raises(ValidationError):
            sr.status = ExecutionStatus.FAILED  # type: ignore[misc]

    def test_round_trip(self) -> None:
        sr = self._sample()
        data = sr.model_dump(mode="json")
        restored = StageResult.model_validate(data)
        assert restored == sr
        # Nested records survive round-trip as the same contract types.
        assert isinstance(restored.issues[0], Issue)
        assert isinstance(restored.metrics[0], MetricValue)
        assert isinstance(restored.artifacts[0], ArtifactRef)


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_common_contracts_do_not_import_heavy_libs() -> None:
    """The common contracts module must not pull heavy compute libraries.

    Importing it must not transitively load polars/pandas/duckdb/numpy/scipy/
    statsmodels. We check ``sys.modules`` after import.
    """
    import sys

    import analytics_platform.contracts.common as common_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by common contracts: {leaked}"


def test_run_id_alias_is_str_compatible() -> None:
    """RunId is a validated string alias usable as a plain str."""
    r: RunId = "run-abc"
    assert r == "run-abc"