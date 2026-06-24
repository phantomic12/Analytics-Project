"""Integration test for the DuckDB connection manager (Build Queue v2.1 Task 112)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analytics_platform.backends.duckdb_connection import DuckDBConnectionManager
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)


@pytest.fixture
def csv_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["a", "b", "c"])
        writer.writerow([1, 2, 3])
        writer.writerow([4, 5, 6])
    return path


class TestDuckDBIntegration:
    def test_load_and_query(self, csv_dataset: Path) -> None:
        manager = DuckDBConnectionManager()
        try:
            manager.execute("CREATE TABLE raw (a INTEGER, b INTEGER, c INTEGER)")
            manager.execute(
                f"INSERT INTO raw SELECT * FROM read_csv_auto('{csv_dataset.as_posix()}')"
            )
            result = manager.execute("SELECT COUNT(*) FROM raw")
            assert result.row_count == 1
            assert result.rows[0][0] == 2
        finally:
            manager.close()
