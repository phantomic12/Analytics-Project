"""Local dataset readers (Build Queue v2.1 Task 86).

This module is the canonical local-filesystem dataset reader.
It takes a typed
:class:`analytics_platform.contracts.datasets.DatasetLoadRequest`
and returns a typed :class:`DatasetLoadResult` that wraps a
``BackendObjectRef`` pointing at the loaded Polars frame. The
reader uses Polars' native Parquet / CSV / TSV / JSON / JSONL
IO.

Per the architecture-test plan (section 5), the ``io`` module is
a domain module and may import from contracts, core, the
backends registry (Task 83), the artifact store (Task 84), and
the approved runtime libraries.

Scope (Task 86):

- :class:`LocalDatasetReader`: the canonical local reader.
  Implements ``read`` for the MVP-supported formats (Parquet,
  CSV, TSV, JSON, JSONL).
- :func:`read_dataset`: the module-level helper that opens the
  reader and reads.
- :class:`DatasetReaderError`: typed exception carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from analytics_platform.backends import PolarsBackend
from analytics_platform.contracts.common import (
    ExecutionStatus,
    Issue,
    Severity,
)
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetFingerprint,
    DatasetHandle,
    DatasetLoadRequest,
    DatasetLoadResult,
    DatasetMaterializationStatus,
    DatasetRole,
    IngestionReport,
    SourceFileMetadata,
    StorageBackend,
)
from analytics_platform.core import (
    AnalyticsPlatformError,
    get_logger,
)

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl

__all__ = [
    "LocalDatasetReader",
    "read_dataset",
    "DatasetReaderError",
]


_LOGGER = get_logger("io.local_reader")


class DatasetReaderError(AnalyticsPlatformError):
    """A typed dataset-reader failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


class LocalDatasetReader:
    """The canonical local-filesystem dataset reader.

    The reader wraps a :class:`PolarsBackend` and uses Polars'
    native IO for the MVP-supported formats. The reader is
    intentionally minimal: it does not auto-detect format (the
    caller provides the request); it does not apply schema
    validation (a separate stage); and it does not write
    anything (writing is the artifact store's job).

    Construction parameters:

    - ``backend``: the :class:`PolarsBackend` to register the
      loaded frames under. Defaults to the canonical default
      backend (see ``backends.registry.default_backend``).
    """

    def __init__(self, backend: PolarsBackend | None = None) -> None:
        if backend is None:
            from analytics_platform.backends.registry import default_backend

            backend = default_backend()
        self._backend = backend

    @property
    def backend(self) -> PolarsBackend:
        return self._backend

    def read(self, request: DatasetLoadRequest) -> DatasetLoadResult:
        """Read ``request.source_uri`` as a Polars frame and
        return the typed result.

        The result wraps a ``BackendObjectRef`` pointing at the
        loaded frame in the backend's registry; the caller can
        resolve the ref to the actual Polars frame via
        :meth:`PolarsBackend.resolve`.
        """
        try:
            import polars as pl  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DatasetReaderError(
                _make_issue(
                    code="POLARS_NOT_INSTALLED",
                    message=(
                        "Polars is required for the local dataset reader "
                        f"but is not installed: {exc}"
                    ),
                )
            ) from exc

        source_path = Path(request.source_uri)
        if not source_path.exists():
            raise DatasetReaderError(
                _make_issue(
                    code="DATASET_FILE_NOT_FOUND",
                    message=f"Dataset file not found: {source_path}",
                )
            )

        fmt = request.format
        try:
            if fmt is DatasetFormat.PARQUET:
                df = pl.read_parquet(str(source_path))
            elif fmt is DatasetFormat.CSV:
                df = pl.read_csv(str(source_path))
            elif fmt is DatasetFormat.TSV:
                df = pl.read_csv(str(source_path), separator="\t")
            elif fmt is DatasetFormat.JSON:
                df = pl.read_json(str(source_path))
            elif fmt is DatasetFormat.JSONL:
                df = pl.read_ndjson(str(source_path))
            else:
                raise DatasetReaderError(
                    _make_issue(
                        code="DATASET_FORMAT_UNSUPPORTED",
                        message=(
                            f"Dataset format {fmt.value!r} is not supported by the local reader"
                        ),
                    )
                )
        except DatasetReaderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DatasetReaderError(
                _make_issue(
                    code="DATASET_READ_FAILED",
                    message=(f"Failed to read {source_path} as {fmt.value}: {exc}"),
                )
            ) from exc

        ref = self._backend.register(df)
        size_bytes = source_path.stat().st_size
        # ``DatasetFingerprint`` requires a content_hash. We
        # compute the SHA-256 of the file bytes here so the
        # fingerprint is self-describing; the alternative
        # (size-only) fingerprint is reserved for non-file
        # sources.
        import hashlib

        content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        fingerprint = DatasetFingerprint(
            algorithm="sha256",
            content_hash=content_hash,
            source=SourceFileMetadata(
                uri=str(source_path),
                size_bytes=size_bytes,
            ),
            row_count=df.height,
        )
        ingestion = IngestionReport(
            detected_format=fmt,
            requested_format=fmt,
            rows_read=df.height,
            bytes_read=size_bytes,
            fingerprint=fingerprint,
            source=SourceFileMetadata(
                uri=str(source_path),
                size_bytes=size_bytes,
            ),
        )
        handle = DatasetHandle(
            dataset_id=f"ds-{Path(request.source_uri).stem}",
            dataset_ref=f"ds-{request.source_uri}",
            name=Path(request.source_uri).stem,
            format=fmt,
            storage_backend=StorageBackend.LOCAL_FS,
            materialization_status=DatasetMaterializationStatus.MATERIALIZED,
            source_uri=str(source_path),
            fingerprint=fingerprint,
            row_count_estimate=df.height,
            role=DatasetRole.SOURCE,
        )
        _LOGGER.info(
            "Loaded dataset: source=%s format=%s rows=%d cols=%d size_bytes=%s",
            source_path,
            fmt.value,
            df.height,
            df.width,
            size_bytes,
        )
        return DatasetLoadResult(
            request=request,
            status=ExecutionStatus.SUCCEEDED,
            handle=handle,
            ingestion=ingestion,
        )


def read_dataset(request: DatasetLoadRequest) -> DatasetLoadResult:
    """Read a dataset using the module-level default reader.

    A convenience wrapper around :meth:`LocalDatasetReader.read`
    that uses the canonical default Polars backend.
    """
    reader = LocalDatasetReader()
    return reader.read(request)
