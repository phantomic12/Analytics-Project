"""Association diagnostics integration test (Build Queue v2.1 Task 111)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analytics_platform.associations.diagnostics import run_association_checks
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import PipelineStageName
from analytics_platform.profiling.summaries import compute_summaries


def _read_csv(path: Path) -> dict:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    cols = rows[0].keys()
    return {col: [float(r[col]) for r in rows] for col in cols}


class TestAssociationDiagnosticsIntegration:
    def test_association_diagnostics_integration(self) -> None:
        fixture = (
            Path(__file__).parent.parent
            / "fixtures"
            / "datasets"
            / "association_diagnostics.csv"
        )
        data = _read_csv(fixture)
        handle = DatasetHandle(
            dataset_id="assoc",
            dataset_ref=DatasetRef("association-diagnostics"),
            name="association diagnostics",
            format=DatasetFormat.CSV,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.REGISTERED,
        )
        profile = compute_summaries(data, dataset=handle)
        assert PipelineStageName.DISTRIBUTION_PROFILING is not None
        report = run_association_checks(handle, profile, values=data)
        assert len(report.pairwise_summaries) > 0
        assert any(pair.score == pytest.approx(1.0) for pair in report.pairwise_summaries)
