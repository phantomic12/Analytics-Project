"""Tests for IO format detection (Build Queue v2.1 Task 81)."""

from __future__ import annotations

import pytest

from analytics_platform.contracts.datasets import DatasetFormat
from analytics_platform.io import (
    FormatDetectionReport,
    detect_format,
    detect_format_from_path,
    is_supported_format,
)


class TestDetectFormatFromPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/data/orders.csv", DatasetFormat.CSV),
            ("/data/orders.tsv", DatasetFormat.TSV),
            ("/data/orders.parquet", DatasetFormat.PARQUET),
            ("/data/orders.json", DatasetFormat.JSON),
            ("/data/orders.jsonl", DatasetFormat.JSONL),
            ("/data/orders.ndjson", DatasetFormat.JSONL),
            ("/data/orders.CSV", DatasetFormat.CSV),  # case-insensitive
            ("/data/orders.unknown", DatasetFormat.UNKNOWN),
            ("/data/no_extension", DatasetFormat.UNKNOWN),
            ("", DatasetFormat.UNKNOWN),
        ],
    )
    def test_detect(self, path: str, expected: DatasetFormat) -> None:
        fmt, confidence = detect_format_from_path(path)
        assert fmt is expected
        if expected is DatasetFormat.UNKNOWN:
            assert confidence == 0.0
        else:
            assert confidence == 1.0


class TestIsSupportedFormat:
    def test_supported(self) -> None:
        for fmt in (
            DatasetFormat.CSV,
            DatasetFormat.TSV,
            DatasetFormat.JSON,
            DatasetFormat.JSONL,
            DatasetFormat.PARQUET,
        ):
            assert is_supported_format(fmt) is True

    def test_unknown_not_supported(self) -> None:
        assert is_supported_format(DatasetFormat.UNKNOWN) is False


class TestDetectFormat:
    def test_basic_parquet(self, tmp_path) -> None:
        path = str(tmp_path / "orders.parquet")
        report = detect_format(path)
        assert isinstance(report, FormatDetectionReport)
        assert report.format is DatasetFormat.PARQUET
        assert report.confidence == 1.0
        assert report.warnings == ()
        assert report.suggested_uri is not None
        assert report.suggested_uri.endswith("orders.parquet")

    def test_unknown_format_emits_warning(self) -> None:
        report = detect_format("/data/orders.bin")
        assert report.format is DatasetFormat.UNKNOWN
        assert len(report.warnings) == 1
        assert report.warnings[0].code == "FORMAT_UNKNOWN"

    def test_to_issue_if_unknown_issue(self) -> None:
        report = detect_format("/data/x.bin")
        issue = report.to_issue_if_unknown()
        assert issue is not None
        assert issue.code == "FORMAT_UNKNOWN"

    def test_to_issue_if_known_returns_none(self) -> None:
        report = detect_format("/data/x.csv")
        assert report.to_issue_if_unknown() is None

    def test_empty_path(self) -> None:
        report = detect_format("")
        assert report.format is DatasetFormat.UNKNOWN
        assert report.source_path is None
        assert report.suggested_uri is None
