"""Canonical lineage store (Build Queue v2.1 Task 88).

This module is the canonical in-process lineage store. It is the
append-only store of :class:`LineageRecord` entries that the
catalog dataset registry and the pipeline stages write into. The
store supports point lookups by :class:`LineageId` and snapshot
queries by :class:`RunId` so reporting and audit stages can
reconstruct a per-run lineage graph without re-walking the entire
record stream.

Per the architecture-test plan (section 5), the ``catalog`` module
is a domain module and may import from contracts, core, and other
domain modules (datasets, backends, artifact_store). The lineage
store is intentionally lightweight: it does not index by
:class:`DatasetId` because the lineage records already carry
``SourceDatasetRef`` / ``DerivedDatasetRef`` pointers and the MVP
workload is single-process, single-run.

Scope (Task 88):

- :class:`LineageStore` — the canonical in-process lineage store.
- :func:`record_lineage` — module-level convenience helper that
  appends a record to the singleton store and returns the
  assigned :class:`LineageId`.
- :func:`get_lineage_store` — returns the module-level singleton
  store. Tests should call :meth:`LineageStore.reset` rather than
  re-bind the module attribute.
- :class:`LineageStoreError` — typed exception carrying an
  :class:`Issue` payload.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from analytics_platform.contracts.common import (
    Issue,
    LineageId,
    RunId,
    Severity,
)
from analytics_platform.contracts.lineage import (
    LineageGraphSnapshot,
    LineageRecord,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "LineageStore",
    "LineageStoreError",
    "record_lineage",
    "get_lineage_store",
]


_LOGGER = get_logger("catalog.lineage_store")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for lineage-store error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


class LineageStoreError(AnalyticsPlatformError):
    """A typed lineage-store failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class LineageStore:
    """The canonical in-process lineage store.

    The store keeps a list of :class:`LineageRecord` in insertion
    order and a ``record_id -> record`` index for O(1) point
    lookups. Snapshot queries (``snapshot_for_run``) filter by
    ``run_id`` and produce a :class:`LineageGraphSnapshot` for the
    consumer.

    Construction parameters:

    - ``id_factory``: optional callable returning a fresh id
      string. Defaults to ``uuid.uuid4().hex``. The factory is
      reserved for future use (id re-writing); the MVP relies on
      :class:`LineageRecord.lineage_id` directly.
    """

    def __init__(self, *, id_factory: "Any | None" = None) -> None:
        self._lock = threading.RLock()
        self._records: list[LineageRecord] = []
        self._by_id: dict[LineageId, LineageRecord] = {}
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------
    def append(self, record: LineageRecord) -> LineageRecord:
        """Append ``record`` to the store.

        The store rejects records whose :data:`LineageId` is
        already present (duplicate append) so a buggy caller
        cannot silently double-record a transformation. The
        function returns the stored record unchanged.
        """
        with self._lock:
            if record.lineage_id in self._by_id:
                raise LineageStoreError(
                    _make_issue(
                        code="LINEAGE_DUPLICATE_ID",
                        message=(
                            f"LineageRecord with lineage_id={record.lineage_id!r} "
                            "is already in the store."
                        ),
                    )
                )
            self._records.append(record)
            self._by_id[record.lineage_id] = record
            _LOGGER.info(
                "Recorded lineage: id=%s operation=%s run_id=%s",
                record.lineage_id,
                record.operation.value,
                record.run_id,
            )
            return record

    def extend(self, records: "list[LineageRecord] | tuple[LineageRecord, ...]") -> None:
        """Append a sequence of records to the store.

        The appends happen in order; the function raises
        :class:`LineageStoreError` on the first duplicate id and
        leaves the store partially-populated (callers can retry
        with the remaining records after resolving the conflict).
        """
        with self._lock:
            for record in records:
                self.append(record)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def get(self, lineage_id: LineageId) -> LineageRecord:
        """Return the :class:`LineageRecord` for ``lineage_id``.

        Raises :class:`LineageStoreError` when no record has that
        id.
        """
        with self._lock:
            try:
                return self._by_id[lineage_id]
            except KeyError as exc:
                raise LineageStoreError(
                    _make_issue(
                        code="LINEAGE_LOOKUP_MISS",
                        message=f"No lineage record with id={lineage_id!r}",
                    )
                ) from exc

    def try_get(self, lineage_id: LineageId) -> LineageRecord | None:
        """Return the :class:`LineageRecord` for ``lineage_id`` or ``None``."""
        with self._lock:
            return self._by_id.get(lineage_id)

    def records_for_run(self, run_id: RunId) -> tuple[LineageRecord, ...]:
        """Return the tuple of records recorded under ``run_id``.

        The records are returned in insertion order; the snapshot
        helper consumes them as-is.
        """
        with self._lock:
            return tuple(r for r in self._records if r.run_id == run_id)

    def snapshot_for_run(
        self,
        run_id: RunId,
        *,
        snapshot_id: str | None = None,
    ) -> LineageGraphSnapshot:
        """Return a :class:`LineageGraphSnapshot` for ``run_id``.

        Raises :class:`LineageStoreError` when no records exist
        for ``run_id`` (the contract requires at least one).
        """
        with self._lock:
            records = self.records_for_run(run_id)
            if not records:
                raise LineageStoreError(
                    _make_issue(
                        code="LINEAGE_EMPTY_RUN",
                        message=f"No lineage records for run_id={run_id!r}",
                    )
                )
            stage_ids = tuple(
                sorted({r.stage_id for r in records if r.stage_id is not None})
            )
            root_ids = tuple(
                sorted(
                    {
                        src.dataset_id
                        for r in records
                        for src in r.sources
                        if r.derived is None or r.derived.dataset_id != src.dataset_id
                    }
                )
            )
            return LineageGraphSnapshot(
                snapshot_id=snapshot_id or self._id_factory(),
                run_id=run_id,
                records=records,
                captured_at=None,
                root_dataset_ids=root_ids,
                stage_ids=stage_ids,
                issues=(),
                warnings=(),
                metadata=None,
            )

    def list(self) -> tuple[LineageRecord, ...]:
        """Return every record in the store (insertion order)."""
        with self._lock:
            return tuple(self._records)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def reset(self) -> None:
        """Clear the store (intended for tests)."""
        with self._lock:
            self._records.clear()
            self._by_id.clear()


# Module-level singleton store. Tests that need a clean state
# should call :meth:`LineageStore.reset` rather than re-bind the
# module attribute.
_STORE = LineageStore()


def get_lineage_store() -> LineageStore:
    """Return the module-level singleton :class:`LineageStore`."""
    return _STORE


def record_lineage(record: LineageRecord) -> LineageRecord:
    """Append ``record`` to the singleton store.

    Returns the stored record unchanged. Use
    :class:`LineageStoreError` to detect duplicate ids.
    """
    return _STORE.append(record)