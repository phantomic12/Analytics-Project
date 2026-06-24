"""Tests for the local dataset reader (Build Queue v2.1 Task 86)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from analytics_platform.backends import PolarsBackend
from analytics_platform.backends.registry import default_backend_id
from analytics_platform.contracts.common import ExecutionStatus
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetLoadRequest,
)
from analytics_platform.io.local_reader import (
    DatasetReaderError,
    LocalDatasetReader,
    read_dataset,
)


@pytest.fixture
def reader() -> LocalDatasetReader:
    return LocalDatasetReader(
        backend=PolarsBackend.from_config(default_backend_id())
    )


def _write_parquet(path: Path) -> Path:
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    df.write_parquet(str(path))
    return path


def _write_csv(path: Path) -> Path:
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    df.write_csv(str(path))
    return path


class TestLocalDatasetReader:
    def test_read_parquet(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        path = _write_parquet(tmp_path / "orders.parquet")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.PARQUET
        )
        result = reader.read(req)
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.handle is not None
        assert result.handle.format is DatasetFormat.PARQUET
        assert result.ingestion.rows_read == 3
        assert result.ingestion.bytes_read > 0
        # The backend object ref points to a DataFrame we can resolve.
        # The backend's ``_registry`` should now contain one
        # frame under a fresh handle.
        assert len(reader.backend._registry) == 1  # type: ignore[attr-defined]  # noqa: SLF001

    def test_read_csv(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        path = _write_csv(tmp_path / "orders.csv")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.CSV
        )
        result = reader.read(req)
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.ingestion.rows_read == 3

    def test_read_tsv(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        # Build a TSV file manually since Polars' write_csv
        # doesn't expose TSV directly.
        path = tmp_path / "orders.tsv"
        path.write_text("a\tb\n1\tx\n2\ty\n3\tz\n", encoding="utf-8")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.TSV
        )
        result = reader.read(req)
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.ingestion.rows_read == 3

    def test_read_json(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        path = tmp_path / "orders.json"
        path.write_text('[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]', encoding="utf-8")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.JSON
        )
        result = reader.read(req)
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.ingestion.rows_read == 2

    def test_read_jsonl(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        path = tmp_path / "orders.jsonl"
        path.write_text('{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n', encoding="utf-8")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.JSONL
        )
        result = reader.read(req)
        assert result.status is ExecutionStatus.SUCCEEDED

    def test_file_not_found(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        req = DatasetLoadRequest(
            source_uri=str(tmp_path / "missing.parquet"),
            format=DatasetFormat.PARQUET,
        )
        with pytest.raises(DatasetReaderError) as ei:
            reader.read(req)
        assert ei.value.issue.code == "DATASET_FILE_NOT_FOUND"

    def test_unsupported_format(
        self, reader: LocalDatasetReader, tmp_path: Path
    ) -> None:
        path = _write_parquet(tmp_path / "x.bin")
        req = DatasetLoadRequest(
            source_uri=str(path),
            format=DatasetFormat.UNKNOWN,
        )
        with pytest.raises(DatasetReaderError) as ei:
            reader.read(req)
        assert ei.value.issue.code == "DATASET_FORMAT_UNSUPPORTED"


class TestModuleLevelHelper:
    def test_read_dataset_helper(self, tmp_path: Path) -> None:
        path = _write_parquet(tmp_path / "x.parquet")
        req = DatasetLoadRequest(
            source_uri=str(path), format=DatasetFormat.PARQUET
        )
        result = read_dataset(req)
        assert result.status is ExecutionStatus.SUCCEEDED
