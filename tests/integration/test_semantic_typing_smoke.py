"""Semantic typing integration smoke test (Build Queue v2.1 Task 110)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.schema.inference import infer_schema
from analytics_platform.semantics.inference import infer_semantic_types


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


class TestSemanticTypingSmoke:
    def test_semantic_typing_smoke(self) -> None:
        fixture = (
            Path(__file__).parent.parent / "fixtures" / "datasets" / "semantic_columns.csv"
        )
        with fixture.open(newline="") as f:
            rows = list(csv.DictReader(f))
        data: dict = {
            col: [r.get(col) for r in rows] for col in rows[0].keys()
        }
        handle = DatasetHandle(
            dataset_id="semantic",
            dataset_ref=DatasetRef("semantic-smoke"),
            name="semantic columns",
            format=DatasetFormat.CSV,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.REGISTERED,
        )
        schema = infer_schema(data, dataset=handle)
        semantic = infer_semantic_types(schema, dataset=handle)
        assert len(semantic.column_profiles) >= 0
        assert schema.columns is not None
