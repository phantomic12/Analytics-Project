"""Tests for pipeline contracts (Build Queue v2.1 Tasks 42-45)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.pipeline import (
    AnalysisPlan,
    AnalysisRunResult,
    PipelineExecutionMode,
    PipelineFailurePolicy,
    PipelineStageName,
    PipelineWarningSummary,
    RunManifest,
    RunManifestRequest,
    RunStatus,
)
from analytics_platform.contracts.registry import (
    RegistryWriteResult,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        plan_id="p1",
        datasets=(_handle(),),
        stages=(PipelineStageName.DATASET_LOAD,),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestEnums:
    def test_stage_names(self) -> None:
        assert PipelineStageName.CONFIG_LOAD.value == "config_load"
        assert PipelineStageName.DATASET_LOAD.value == "dataset_load"
        assert PipelineStageName.OLS_FIT.value == "ols_fit"
        assert PipelineStageName.FILE_BASED_REGISTRY_WRITING.value == "file_based_registry_writing"

    def test_execution_modes(self) -> None:
        assert PipelineExecutionMode.NORMAL.value == "normal"
        assert PipelineExecutionMode.DRY_RUN.value == "dry_run"
        assert PipelineExecutionMode.REPLAY.value == "replay"
        assert PipelineExecutionMode.PROFILE_ONLY.value == "profile_only"

    def test_failure_policies(self) -> None:
        assert PipelineFailurePolicy.FAIL_FAST.value == "fail_fast"
        assert PipelineFailurePolicy.CONTINUE_WITH_WARNINGS.value == "continue_with_warnings"


# ---------------------------------------------------------------------------
# AnalysisPlan
# ---------------------------------------------------------------------------
class TestAnalysisPlan:
    def test_basic(self) -> None:
        p = _plan()
        assert p.execution_mode is PipelineExecutionMode.NORMAL
        assert p.failure_policy is PipelineFailurePolicy.FAIL_FAST

    def test_empty_datasets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(),
                stages=(PipelineStageName.DATASET_LOAD,),
            )

    def test_empty_stages_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(_handle(),),
                stages=(),
            )

    def test_target_dataset_index_in_range(self) -> None:
        AnalysisPlan(
            plan_id="p1",
            datasets=(_handle(), _handle()),
            stages=(PipelineStageName.DATASET_LOAD,),
            target_dataset_index=1,
        )

    def test_target_dataset_index_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(_handle(),),
                stages=(PipelineStageName.DATASET_LOAD,),
                target_dataset_index=5,
            )

    def test_duplicate_stages_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(_handle(),),
                stages=(
                    PipelineStageName.DATASET_LOAD,
                    PipelineStageName.DATASET_LOAD,
                ),
            )

    def test_negative_max_runtime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(_handle(),),
                stages=(PipelineStageName.DATASET_LOAD,),
                max_runtime_seconds=-1,
            )

    def test_round_trip(self) -> None:
        p = _plan()
        assert AnalysisPlan.model_validate(p.model_dump(mode="json")) == p


# ---------------------------------------------------------------------------
# RunManifest
# ---------------------------------------------------------------------------
class TestRunManifest:
    def _manifest(self) -> RunManifest:
        return RunManifest(
            manifest_id="m1",
            run_id="r1",
            plan=_plan(),
        )

    def test_basic(self) -> None:
        m = self._manifest()
        assert m.stage_statuses == ()

    def test_duplicate_stage_statuses_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunManifest(
                manifest_id="m1",
                run_id="r1",
                plan=_plan(),
                stage_statuses=(
                    ("s1", RunStatus.SUCCEEDED),
                    ("s1", RunStatus.FAILED),
                ),
            )

    def test_finished_before_started_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunManifest(
                manifest_id="m1",
                run_id="r1",
                plan=_plan(),
                started_at=datetime(2026, 6, 20, 18, 5, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc),
            )

    def test_naive_timestamps_normalized(self) -> None:
        m = RunManifest(
            manifest_id="m1",
            run_id="r1",
            plan=_plan(),
            started_at=datetime(2026, 6, 20, 18, 0, 0),
            finished_at=datetime(2026, 6, 20, 18, 5, 0),
        )
        for attr in ("started_at", "finished_at"):
            value = getattr(m, attr)
            assert value is not None
            assert value.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        m = self._manifest()
        assert RunManifest.model_validate(m.model_dump(mode="json")) == m


# ---------------------------------------------------------------------------
# RunManifestRequest
# ---------------------------------------------------------------------------
class TestRunManifestRequest:
    def test_basic(self) -> None:
        r = RunManifestRequest(plan=_plan())
        assert r.dataset_fingerprints == ()

    def test_with_fingerprints(self) -> None:
        r = RunManifestRequest(
            plan=_plan(),
            dataset_fingerprints=(("d1", "abc"),),
            config_hash="cfg",
            lineage_snapshot_id="lin-1",
            artifact_ids=("a1",),
        )
        assert r.config_hash == "cfg"


# ---------------------------------------------------------------------------
# PipelineWarningSummary
# ---------------------------------------------------------------------------
class TestPipelineWarningSummary:
    def test_basic(self) -> None:
        s = PipelineWarningSummary()
        assert s.total_warning_count is None

    def test_duplicate_severities_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PipelineWarningSummary(
                warnings_by_severity=(
                    (Severity.WARNING, 1),
                    (Severity.WARNING, 2),
                ),
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PipelineWarningSummary(total_warning_count=-1)
        with pytest.raises(ValidationError):
            PipelineWarningSummary(
                warnings_by_severity=((Severity.WARNING, -1),),
            )

    def test_round_trip(self) -> None:
        s = PipelineWarningSummary(total_warning_count=5)
        assert PipelineWarningSummary.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# AnalysisRunResult
# ---------------------------------------------------------------------------
class TestAnalysisRunResult:
    def _result(self) -> AnalysisRunResult:
        return AnalysisRunResult(run_id="r1", status=RunStatus.SUCCEEDED, plan=_plan())

    def test_basic(self) -> None:
        r = self._result()
        assert r.report_ids == ()

    def test_with_manifest(self) -> None:
        r = AnalysisRunResult(
            run_id="r1",
            status=RunStatus.SUCCEEDED,
            plan=_plan(),
            manifest=RunManifest(manifest_id="m1", run_id="r1", plan=_plan()),
        )
        assert r.manifest is not None

    def test_with_registry_write_run_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunResult(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                plan=_plan(),
                registry_write=RegistryWriteResult(run_id="r2", wrote_run_record=True),
            )

    def test_with_registry_write_match(self) -> None:
        r = AnalysisRunResult(
            run_id="r1",
            status=RunStatus.SUCCEEDED,
            plan=_plan(),
            registry_write=RegistryWriteResult(run_id="r1", wrote_run_record=True),
        )
        assert r.registry_write is not None

    def test_empty_artifact_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunResult(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                plan=_plan(),
                artifact_paths=("",),
            )

    def test_finished_before_started_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunResult(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                plan=_plan(),
                started_at=datetime(2026, 6, 20, 18, 5, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc),
            )

    def test_duplicate_report_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunResult(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                plan=_plan(),
                report_ids=("r1", "r1"),
            )

    def test_with_issues_and_warnings(self) -> None:
        r = AnalysisRunResult(
            run_id="r1",
            status=RunStatus.FAILED,
            plan=_plan(),
            issues=(Issue(code="I", severity=Severity.ERROR, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
            warning_summary=PipelineWarningSummary(total_warning_count=1),
        )
        assert len(r.issues) == 1

    def test_round_trip(self) -> None:
        r = self._result()
        assert AnalysisRunResult.model_validate(r.model_dump(mode="json")) == r


def test_pipeline_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.pipeline as pipeline_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by pipeline contracts: {leaked}"
