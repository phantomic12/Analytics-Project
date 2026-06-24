"""Tests for the association diagnostics stage (Build Queue v2.1 Task 97)."""

from __future__ import annotations

from analytics_platform.associations.diagnostics import (
    AssociationDiagnostics,
    run_association_checks,
)
from analytics_platform.contracts.associations import (
    AssociationCheckSpec,
    AssociationCheckReport,
)
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.profiling.summaries import compute_summaries


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


def _approx(value: float):
    import pytest
    return pytest.approx(value)


class TestAssociationDiagnostics:
    def test_numeric_pair_produces_summary(self) -> None:
        data = {"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [2.0, 4.0, 6.0, 8.0, 10.0]}
        profile = compute_summaries(data, dataset=_handle())
        report = run_association_checks(
            _handle(),
            profile,
            spec=AssociationCheckSpec(),
            values=data,
        )
        assert isinstance(report, AssociationCheckReport)
        assert len(report.pairwise_summaries) == 1
        assert report.pairwise_summaries[0].column_a == "a"
        assert report.pairwise_summaries[0].column_b == "b"
        assert report.pairwise_summaries[0].score == _approx(1.0)

    def test_non_numeric_pair_warns(self) -> None:
        data = {"a": [1, 2, 3, 4, 5], "c": ["x", "y", "x", "y", "x"]}
        profile = compute_summaries(data, dataset=_handle())
        report = run_association_checks(
            _handle(),
            profile,
            spec=AssociationCheckSpec(),
            values=data,
        )
        assert report.pairwise_summaries == ()
        assert any(w.code == "ASSOCIATION_SKIP_NON_NUMERIC" for w in report.warnings)

    def test_perfect_count_equals_perfect_pairs(self) -> None:
        data = {"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0]}
        profile = compute_summaries(data, dataset=_handle())
        report = run_association_checks(
            _handle(),
            profile,
            spec=AssociationCheckSpec(),
            values=data,
        )
        assert report.perfect_association_count == 1

    def test_class_api_runs(self) -> None:
        data = {"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]}
        profile = compute_summaries(data, dataset=_handle())
        report = AssociationDiagnostics().run(
            _handle(),
            profile,
            spec=AssociationCheckSpec(),
            values=data,
        )
        assert isinstance(report, AssociationCheckReport)
