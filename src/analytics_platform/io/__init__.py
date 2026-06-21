"""IO format detection (Build Queue v2.1 Task 81).

This module is the canonical IO format detection layer for the
analytics platform. The :class:`DatasetFormat` enum is owned by
the ``contracts.datasets`` family; this module is the runtime
*detector* that turns a file path into a
:class:`DatasetFormat` and produces a bounded
:class:`FormatDetectionReport`.

Per the architecture-test plan, the IO module may import from
contracts, core, and the approved runtime libraries. The detector
intentionally uses only the standard library so it stays
lightweight; the *reader* (Task 86) is the layer that imports
Polars.

The detection rules:

- ``.parquet`` -> ``DatasetFormat.PARQUET``
- ``.csv`` -> ``DatasetFormat.CSV``
- ``.tsv`` -> ``DatasetFormat.TSV``
- ``.json`` -> ``DatasetFormat.JSON``
- ``.jsonl`` / ``.ndjson`` -> ``DatasetFormat.JSONL``
- anything else -> ``DatasetFormat.UNKNOWN`` (with a typed
  warning in the report)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetFormat

__all__ = [
    "FormatDetectionReport",
    "detect_format",
    "detect_format_from_path",
    "is_supported_format",
]


@dataclass(frozen=True)
class FormatDetectionReport:
    """A typed IO format detection report.

    The report is intentionally small: a detected
    :class:`DatasetFormat`, a ``confidence`` score in ``[0.0, 1.0]``,
    an optional canonical ``suggested_uri`` (e.g. when a
    relative path is resolved), the optional originating
    ``source_path``, and a tuple of typed warnings. The
    ``confidence`` is ``1.0`` for unambiguous extensions and
    lower for content-based heuristics (not yet implemented
    in the v1.1 MVP — content-based detection is deferred).
    """

    format: DatasetFormat
    confidence: float
    source_path: str | None
    suggested_uri: str | None
    warnings: tuple[WarningRecord, ...]

    def to_issue_if_unknown(self) -> Issue | None:
        """Return a typed :class:`Issue` when the detected format
        is :attr:`DatasetFormat.UNKNOWN`, else ``None``.

        The canonical way to surface an unknown format to
        reporting and the ingestion stage is via
        ``IngestionReport.detected_format`` + ``IngestionReport.issues``.
        This helper is a thin convenience for the loader / reader
        path.
        """
        if self.format is not DatasetFormat.UNKNOWN:
            return None
        return Issue(
            code="FORMAT_UNKNOWN",
            severity=Severity.ERROR,
            message=(
                f"Could not detect a supported dataset format from "
                f"path={self.source_path!r}"
            ),
        )


# Map of lowercased extension -> DatasetFormat. Order matters
# only for documentation; the dict enforces uniqueness.
_EXT_MAP: dict[str, DatasetFormat] = {
    ".parquet": DatasetFormat.PARQUET,
    ".csv": DatasetFormat.CSV,
    ".tsv": DatasetFormat.TSV,
    ".json": DatasetFormat.JSON,
    ".jsonl": DatasetFormat.JSONL,
    ".ndjson": DatasetFormat.JSONL,
}


def is_supported_format(fmt: DatasetFormat) -> bool:
    """Return True if ``fmt`` is a known, supported format.

    ``DatasetFormat.UNKNOWN`` returns ``False``; the canonical
    MVP-supported formats are CSV, TSV, JSON, JSONL, and PARQUET.
    """
    return fmt in (
        DatasetFormat.CSV,
        DatasetFormat.TSV,
        DatasetFormat.JSON,
        DatasetFormat.JSONL,
        DatasetFormat.PARQUET,
    )


def detect_format_from_path(path: str) -> tuple[DatasetFormat, float]:
    """Detect the :class:`DatasetFormat` from a path's extension.

    Returns a tuple of (format, confidence). The confidence is
    ``1.0`` for unambiguous extensions; ``0.0`` for unknown
    formats.

    The function is pure: it does not touch the filesystem.
    """
    if not path:
        return DatasetFormat.UNKNOWN, 0.0
    suffix = Path(path).suffix.lower()
    fmt = _EXT_MAP.get(suffix, DatasetFormat.UNKNOWN)
    return fmt, 1.0 if fmt is not DatasetFormat.UNKNOWN else 0.0


def detect_format(
    path: str,
    *,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> FormatDetectionReport:
    """Detect the format of a dataset at ``path``.

    Returns a :class:`FormatDetectionReport`. When the format
    cannot be detected, the report's ``format`` is
    :attr:`DatasetFormat.UNKNOWN` and a typed :class:`WarningRecord`
    is added to ``warnings``.

    When ``path`` is a relative path, the report's
    ``suggested_uri`` is the absolute resolved path. The
    ``source_path`` is the input verbatim.
    """
    fmt, confidence = detect_format_from_path(path)
    suggested_uri: str | None = None
    try:
        if path:
            suggested_uri = str(Path(path).expanduser().resolve(strict=False))
    except OSError:
        # Path resolution failure is non-fatal; the detector
        # still reports the format from the extension.
        suggested_uri = None
    warnings: list[WarningRecord] = []
    if fmt is DatasetFormat.UNKNOWN:
        warnings.append(
            WarningRecord(
                code="FORMAT_UNKNOWN",
                message=(
                    f"Could not detect a supported dataset format "
                    f"from path={path!r}"
                ),
                stage_id=stage_id,
                run_id=run_id,
            )
        )
    return FormatDetectionReport(
        format=fmt,
        confidence=confidence,
        source_path=path or None,
        suggested_uri=suggested_uri,
        warnings=tuple(warnings),
    )
