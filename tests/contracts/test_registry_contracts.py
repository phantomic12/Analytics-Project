"""Tests for registry contracts (Build Queue v2.1 Task 41)."""

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
from analytics_platform.contracts.modeling import (
    CoefficientTable,
    ModelFamily,
    ModelPurpose,
    ModelResult,
    ModelSpec,
    ModelType,
    OLSModelSpec,
    TargetType,
)
from analytics_platform.contracts.registry import (
    ArtifactRegistryEntry,
    DatasetRegistryEntry,
    ModelRegistryEntry,
    RegistryWriteRequest,
    RegistryWriteResult,
    ResultRegistryEntry,
    RunHistoryQuery,
    RunRegistryRecord,
    RunStatus,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _model_spec() -> ModelSpec:
    return ModelSpec(
        model_id="m1",
        model_type=ModelType.OLS,
        model_family=ModelFamily.LINEAR,
        target_type=TargetType.CONTINUOUS,
        ols_spec=OLSModelSpec(
            target_column="amount",
            predictor_columns=("age",),
        ),
    )


def _model_result() -> ModelResult:
    return ModelResult(
        model_id="m1",
        coefficient_table=CoefficientTable(),
    )


# ---------------------------------------------------------------------------
# RunStatus
# ---------------------------------------------------------------------------
class TestRunStatus:
    def test_known_members(self) -> None:
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCEEDED.value == "succeeded"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.SKIPPED.value == "skipped"
        assert RunStatus.CANCELLED.value == "cancelled"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            RunStatus("queued")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunRegistryRecord
# ---------------------------------------------------------------------------
class TestRunRegistryRecord:
    def test_basic(self) -> None:
        r = RunRegistryRecord(run_id="r1", status=RunStatus.SUCCEEDED)
        assert r.stage_ids == ()
        assert r.progress is None

    def test_full(self) -> None:
        r = RunRegistryRecord(
            run_id="r1",
            status=RunStatus.SUCCEEDED,
            started_at=datetime(2026, 6, 20, 18, 0, 0),
            finished_at=datetime(2026, 6, 20, 18, 5, 0),
            stage_ids=("s1", "s2"),
            config_hash="abc",
            dataset_ids=("d1",),
            model_ids=("m1",),
            artifact_ids=("a1",),
            progress=1.0,
        )
        assert r.progress == 1.0

    def test_duplicate_stage_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRegistryRecord(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                stage_ids=("s1", "s1"),
            )

    def test_finished_before_started_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRegistryRecord(
                run_id="r1",
                status=RunStatus.SUCCEEDED,
                started_at=datetime(2026, 6, 20, 18, 5, 0),
                finished_at=datetime(2026, 6, 20, 18, 0, 0),
            )

    def test_naive_timestamps_normalized(self) -> None:
        r = RunRegistryRecord(
            run_id="r1",
            status=RunStatus.SUCCEEDED,
            started_at=datetime(2026, 6, 20, 18, 0, 0),
            finished_at=datetime(2026, 6, 20, 18, 5, 0),
            registered_at=datetime(2026, 6, 20, 18, 5, 5),
        )
        for attr in ("started_at", "finished_at", "registered_at"):
            value = getattr(r, attr)
            assert value is not None
            assert value.tzinfo is timezone.utc

    def test_progress_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRegistryRecord(
                run_id="r1", status=RunStatus.SUCCEEDED, progress=1.5
            )

    def test_round_trip(self) -> None:
        r = RunRegistryRecord(run_id="r1", status=RunStatus.SUCCEEDED)
        assert RunRegistryRecord.model_validate(
            r.model_dump(mode="json")
        ) == r


# ---------------------------------------------------------------------------
# ResultRegistryEntry
# ---------------------------------------------------------------------------
class TestResultRegistryEntry:
    def test_basic(self) -> None:
        e = ResultRegistryEntry(
            entry_id="e1",
            run_id="r1",
            result_kind="coefficient_table",
            result_id="c1",
        )
        assert e.fingerprint is None

    def test_round_trip(self) -> None:
        e = ResultRegistryEntry(
            entry_id="e1",
            run_id="r1",
            result_kind="x",
            result_id="y",
        )
        assert ResultRegistryEntry.model_validate(
            e.model_dump(mode="json")
        ) == e


# ---------------------------------------------------------------------------
# ModelRegistryEntry
# ---------------------------------------------------------------------------
class TestModelRegistryEntry:
    def test_basic(self) -> None:
        e = ModelRegistryEntry(
            entry_id="e1",
            model_id="m1",
            run_id="r1",
            model_spec=_model_spec(),
        )
        assert e.model_result is None

    def test_with_result(self) -> None:
        e = ModelRegistryEntry(
            entry_id="e1",
            model_id="m1",
            run_id="r1",
            model_spec=_model_spec(),
            model_result=_model_result(),
        )
        assert e.model_result is not None

    def test_model_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelRegistryEntry(
                entry_id="e1",
                model_id="m1",
                run_id="r1",
                model_spec=_model_spec(),
                model_result=ModelResult(
                    model_id="m2", coefficient_table=CoefficientTable()
                ),
            )

    def test_naive_registered_at_normalized(self) -> None:
        e = ModelRegistryEntry(
            entry_id="e1",
            model_id="m1",
            run_id="r1",
            model_spec=_model_spec(),
            registered_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert e.registered_at is not None
        assert e.registered_at.tzinfo is timezone.utc


# ---------------------------------------------------------------------------
# DatasetRegistryEntry
# ---------------------------------------------------------------------------
class TestDatasetRegistryEntry:
    def test_basic(self) -> None:
        e = DatasetRegistryEntry(
            entry_id="e1",
            dataset_id="d1",
            dataset_handle=_handle(),
            run_id="r1",
        )
        assert e.fingerprint is None

    def test_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DatasetRegistryEntry(
                entry_id="e1",
                dataset_id="d1",
                dataset_handle=DatasetHandle(
                    dataset_id="d2", dataset_ref="ds-d2", name="x"
                ),
                run_id="r1",
            )


# ---------------------------------------------------------------------------
# ArtifactRegistryEntry
# ---------------------------------------------------------------------------
class TestArtifactRegistryEntry:
    def test_basic(self) -> None:
        e = ArtifactRegistryEntry(
            entry_id="e1",
            artifact_id="a1",
            artifact_kind="dataset",
            run_id="r1",
            uri="/data/x.parquet",
        )
        assert e.fingerprint is None


# ---------------------------------------------------------------------------
# RegistryWriteRequest / RegistryWriteResult
# ---------------------------------------------------------------------------
class TestRegistryWrite:
    def test_request(self) -> None:
        r = RegistryWriteRequest(
            run_record=RunRegistryRecord(
                run_id="r1", status=RunStatus.SUCCEEDED
            ),
        )
        assert r.overwrite is False

    def test_request_with_entries(self) -> None:
        r = RegistryWriteRequest(
            run_record=RunRegistryRecord(
                run_id="r1", status=RunStatus.SUCCEEDED
            ),
            result_entries=(
                ResultRegistryEntry(
                    entry_id="e1",
                    run_id="r1",
                    result_kind="x",
                    result_id="y",
                ),
            ),
            model_entries=(
                ModelRegistryEntry(
                    entry_id="e2",
                    model_id="m1",
                    run_id="r1",
                    model_spec=_model_spec(),
                ),
            ),
            dataset_entries=(
                DatasetRegistryEntry(
                    entry_id="e3",
                    dataset_id="d1",
                    dataset_handle=_handle(),
                    run_id="r1",
                ),
            ),
            artifact_entries=(
                ArtifactRegistryEntry(
                    entry_id="e4",
                    artifact_id="a1",
                    artifact_kind="dataset",
                    run_id="r1",
                    uri="/x",
                ),
            ),
        )
        assert len(r.result_entries) == 1

    def test_request_duplicate_entry_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegistryWriteRequest(
                run_record=RunRegistryRecord(
                    run_id="r1", status=RunStatus.SUCCEEDED
                ),
                result_entries=(
                    ResultRegistryEntry(
                        entry_id="e1",
                        run_id="r1",
                        result_kind="x",
                        result_id="y",
                    ),
                    ResultRegistryEntry(
                        entry_id="e1",
                        run_id="r1",
                        result_kind="x",
                        result_id="y",
                    ),
                ),
            )

    def test_result(self) -> None:
        r = RegistryWriteResult(
            run_id="r1", wrote_run_record=True, result_entry_count=1
        )
        assert r.issues == ()

    def test_result_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegistryWriteResult(
                run_id="r1", wrote_run_record=True, result_entry_count=-1
            )

    def test_result_naive_written_at_normalized(self) -> None:
        r = RegistryWriteResult(
            run_id="r1",
            wrote_run_record=True,
            written_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.written_at is not None
        assert r.written_at.tzinfo is timezone.utc


# ---------------------------------------------------------------------------
# RunHistoryQuery
# ---------------------------------------------------------------------------
class TestRunHistoryQuery:
    def test_basic(self) -> None:
        q = RunHistoryQuery()
        assert q.limit is None

    def test_until_before_since_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunHistoryQuery(
                since=datetime(2026, 6, 20, 18, 5, 0, tzinfo=timezone.utc),
                until=datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc),
            )

    def test_negative_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunHistoryQuery(limit=-1)

    def test_naive_timestamps_normalized(self) -> None:
        q = RunHistoryQuery(
            since=datetime(2026, 6, 20, 18, 0, 0),
            until=datetime(2026, 6, 20, 18, 5, 0),
            status_filter=RunStatus.SUCCEEDED,
            run_id_prefix="r-",
        )
        assert q.since is not None
        assert q.since.tzinfo is timezone.utc


def test_registry_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.registry as registry_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by registry contracts: {leaked}"
