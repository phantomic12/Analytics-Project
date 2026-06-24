"""Canonical dataset registry (Build Queue v2.1 Task 87).

This module is the canonical in-process dataset registry. It
pairs the contract family's :class:`DatasetHandle` shape with the
:class:`RegisteredDatasetResult` that the catalog produces (carrying
the optional :data:`LineageId` and :data:`ArtifactId`). The registry
sits between the IO layer (which produces a
:class:`DatasetLoadResult`) and the runtime dataset store (Task 85,
which holds the raw :class:`DatasetHandle` for downstream stages).

Per the architecture-test plan (section 5), the ``catalog`` module
is a domain module and may import from contracts, core, the
datasets runtime store (Task 85), the artifact store (Task 84),
and the approved runtime libraries. Reporting and pipeline consume
the registry *through* the typed contract outputs; they never read
the in-process state directly.

Scope (Task 87):

- :class:`DatasetRegistry` — the canonical in-process dataset
  registry keyed by :class:`DatasetId`.
- :func:`register_load_result` — convenience helper that registers
  a :class:`DatasetLoadResult`, writes a corresponding
  :class:`LineageRecord` of operation ``LOAD`` into the lineage
  store, and returns the :class:`RegisteredDatasetResult`.
- :func:`get_dataset_registry` — returns the module-level
  singleton registry (tests should call
  :meth:`DatasetRegistry.reset` rather than re-binding the
  module attribute).
- :class:`DatasetRegistryError` / :class:`DatasetAlreadyRegistered`
  — typed exceptions carrying an :class:`Issue` payload.
- :class:`RegistrationOutcome` — a typed small bundle returned by
  the convenience helper that bundles the
  :class:`RegisteredDatasetResult`, the new :class:`LineageRecord`
  (when the lineage store accepted it), and the in-process
  :class:`DatasetHandle` recorded in the runtime store.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable

from analytics_platform.contracts.common import (
    ArtifactId,
    DatasetId,
    ExecutionStatus,
    Issue,
    LineageId,
    Severity,
)
from analytics_platform.contracts.datasets import (
    DatasetHandle,
    DatasetLoadResult,
    DatasetRef,
    IngestionReport,
    RegisteredDatasetResult,
)
from analytics_platform.contracts.lineage import (
    DerivedDatasetRef,
    LineageOperationType,
    LineageRecord,
    SourceDatasetRef,
    TransformationRef,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger
from analytics_platform.datasets import RuntimeDatasetStore

if TYPE_CHECKING:  # pragma: no cover - import-only
    from analytics_platform.catalog.lineage_store import LineageStore

__all__ = [
    "DatasetRegistry",
    "DatasetAlreadyRegistered",
    "DatasetRegistryError",
    "RegistrationOutcome",
    "get_dataset_registry",
    "register_load_result",
]


_LOGGER = get_logger("catalog.dataset_registry")


def _default_runtime_store() -> RuntimeDatasetStore:
    """Return the module-level :class:`RuntimeDatasetStore` singleton.

    The catalog threads through the datasets package's module-level
    ``_STORE`` singleton so the convenience helpers
    (``register_dataset`` / ``lookup_dataset`` / ...) see what
    the registry writes. Imported lazily so importing the catalog
    module does not pull the datasets package into the import-time
    dependency chain.
    """
    from analytics_platform.datasets import _STORE as _RUNTIME_STORE  # noqa: PLC0415

    return _RUNTIME_STORE


def _utc_now() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (helper for stamping)."""
    return datetime.now(UTC)


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for registry error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


class DatasetRegistryError(AnalyticsPlatformError):
    """A typed dataset-registry failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class DatasetAlreadyRegistered(DatasetRegistryError):
    """Raised when a dataset is registered twice with the same id.

    The MVP treats duplicate registration as a typed failure rather
    than a silent overwrite so that callers must explicitly choose
    to replace a registration (via
    :meth:`DatasetRegistry.replace`). Multi-registration is rare
    and almost always signals a pipeline bug.
    """

    def __init__(self, dataset_id: DatasetId) -> None:
        super().__init__(
            _make_issue(
                code="DATASET_ALREADY_REGISTERED",
                message=(
                    f"Dataset with id={dataset_id!r} is already registered; "
                    "use DatasetRegistry.replace to overwrite."
                ),
            )
        )
        self.dataset_id = dataset_id


class RegistrationOutcome:
    """A typed bundle returned by :func:`register_load_result`.

    The outcome bundles the :class:`RegisteredDatasetResult` (the
    contract-level output) with the runtime :class:`DatasetHandle`
    recorded in the runtime store and the
    :class:`LineageRecord` recorded in the lineage store. The
    outcome is intentionally lightweight — it holds references to
    the live objects rather than copies — so callers can inspect
    any of the three without re-querying.

    Fields:

    - ``result``: the :class:`RegisteredDatasetResult` produced.
    - ``handle``: the :class:`DatasetHandle` written to the runtime
      store.
    - ``lineage_record``: the :class:`LineageRecord` written to the
      lineage store (or ``None`` when no lineage store was wired
      in).
    """

    __slots__ = ("result", "handle", "lineage_record")

    def __init__(
        self,
        *,
        result: RegisteredDatasetResult,
        handle: DatasetHandle,
        lineage_record: LineageRecord | None,
    ) -> None:
        self.result = result
        self.handle = handle
        self.lineage_record = lineage_record


class DatasetRegistry:
    """The canonical in-process dataset registry.

    The registry maps :class:`DatasetId` to the
    :class:`RegisteredDatasetResult` produced at registration time.
    It is process-local; the catalog does not persist the
    in-process map across runs (the artifact store + run manifest
    own cross-run persistence).

    Thread-safety: every public method takes the registry's lock,
    so concurrent registration from multiple threads is safe.

    Construction parameters:

    - ``runtime_store``: optional :class:`RuntimeDatasetStore` to
      write the raw :class:`DatasetHandle` to. Defaults to a fresh
      in-process store.
    - ``lineage_store``: optional :class:`LineageStore` to record
      the ``LOAD`` :class:`LineageRecord` into. ``None`` disables
      lineage recording (useful for tests).
    - ``clock``: optional callable returning a timezone-aware
      :class:`datetime` for the ``registered_at`` /
      ``recorded_at`` fields. Defaults to :func:`_utc_now`.
    - ``id_factory``: optional callable returning a fresh id
      string for the :data:`LineageId` / :data:`ArtifactId`
      defaults. Defaults to ``uuid.uuid4().hex``.
    """

    def __init__(
        self,
        *,
        runtime_store: RuntimeDatasetStore | None = None,
        lineage_store: "LineageStore | None" = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        # The catalog threads through the module-level singleton
        # ``RuntimeDatasetStore`` so the convenience helpers
        # (``register_dataset`` / ``lookup_dataset``) see what the
        # registry wrote. Tests that need isolation can still
        # inject their own store via the ``runtime_store`` kwarg,
        # but the default always uses the singleton.
        self._runtime_store = runtime_store or _default_runtime_store()
        self._lineage_store = lineage_store
        self._clock = clock or _utc_now
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._results: dict[DatasetId, RegisteredDatasetResult] = {}
        self._handles: dict[DatasetId, DatasetHandle] = {}

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def get(self, dataset_id: DatasetId) -> RegisteredDatasetResult:
        """Return the registration result for ``dataset_id``.

        Raises :class:`DatasetRegistryError` when no dataset has
        been registered under ``dataset_id``.
        """
        with self._lock:
            try:
                return self._results[dataset_id]
            except KeyError as exc:
                raise DatasetRegistryError(
                    _make_issue(
                        code="DATASET_REGISTRY_LOOKUP_MISS",
                        message=(
                            f"No dataset registered under id={dataset_id!r}"
                        ),
                    )
                ) from exc

    def try_get(self, dataset_id: DatasetId) -> RegisteredDatasetResult | None:
        """Return the registration result for ``dataset_id`` or ``None``."""
        with self._lock:
            return self._results.get(dataset_id)

    def get_handle(self, dataset_id: DatasetId) -> DatasetHandle:
        """Return the :class:`DatasetHandle` registered under ``dataset_id``.

        Raises :class:`DatasetRegistryError` when no dataset has
        been registered under ``dataset_id``.
        """
        with self._lock:
            try:
                return self._handles[dataset_id]
            except KeyError as exc:
                raise DatasetRegistryError(
                    _make_issue(
                        code="DATASET_REGISTRY_LOOKUP_MISS",
                        message=(
                            f"No dataset handle registered under id={dataset_id!r}"
                        ),
                    )
                ) from exc

    def list(self) -> list[DatasetId]:
        """Return the sorted list of registered dataset ids."""
        with self._lock:
            return sorted(self._results)

    def known(self) -> list[DatasetId]:
        """Return the sorted list of registered dataset ids (alias of ``list``)."""
        return self.list()

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------
    def register(
        self,
        handle: DatasetHandle,
        *,
        ingestion: IngestionReport,
        artifact_id: ArtifactId | None = None,
        run_id: Any = None,
        stage_id: Any = None,
    ) -> RegisteredDatasetResult:
        """Register ``handle`` and return the typed result.

        The :class:`DatasetHandle` is also written to the runtime
        store so downstream stages can look it up by id. A
        :class:`LineageRecord` of operation ``LOAD`` is recorded in
        the lineage store when one is wired in. The handle's
        ``registered_at`` field is stamped if not already set.

        ``ingestion`` is required because the
        :class:`RegisteredDatasetResult` contract requires it.
        Callers that have a real :class:`IngestionReport` should
        pass it directly; synthetic tests can use
        :func:`register_load_result` or build a minimal
        :class:`IngestionReport` themselves.

        Raises :class:`DatasetAlreadyRegistered` when the id is
        already present; use :meth:`replace` to overwrite.
        """
        with self._lock:
            if handle.dataset_id in self._results:
                raise DatasetAlreadyRegistered(handle.dataset_id)
            stamped = self._stamp_handle(handle)
            self._runtime_store.register(stamped)
            self._handles[stamped.dataset_id] = stamped
            result = self._build_result(
                handle=stamped,
                ingestion=ingestion,
                artifact_id=artifact_id,
                lineage_id=None,
                run_id=run_id,
                stage_id=stage_id,
            )
            self._results[stamped.dataset_id] = result
            if self._lineage_store is not None:
                record = self._build_load_lineage(stamped, result)
                self._lineage_store.append(record)
                result = result.model_copy(update={"lineage_id": record.lineage_id})
                self._results[stamped.dataset_id] = result
            _LOGGER.info(
                "Registered dataset: id=%s name=%s source_uri=%s",
                stamped.dataset_id,
                stamped.name,
                stamped.source_uri,
            )
            return result

    def replace(
        self,
        handle: DatasetHandle,
        *,
        ingestion: IngestionReport,
        artifact_id: ArtifactId | None = None,
        run_id: Any = None,
        stage_id: Any = None,
    ) -> RegisteredDatasetResult:
        """Replace an existing registration (or register a new one).

        Unlike :meth:`register`, ``replace`` silently overwrites an
        existing entry with the same :class:`DatasetId`. It is the
        canonical API for re-ingesting a dataset whose fingerprint
        changed.
        """
        with self._lock:
            stamped = self._stamp_handle(handle)
            self._runtime_store.register(stamped)
            self._handles[stamped.dataset_id] = stamped
            result = self._build_result(
                handle=stamped,
                ingestion=ingestion,
                artifact_id=artifact_id,
                lineage_id=None,
                run_id=run_id,
                stage_id=stage_id,
            )
            self._results[stamped.dataset_id] = result
            if self._lineage_store is not None:
                record = self._build_load_lineage(stamped, result)
                self._lineage_store.append(record)
                result = result.model_copy(update={"lineage_id": record.lineage_id})
                self._results[stamped.dataset_id] = result
            _LOGGER.info(
                "Replaced dataset registration: id=%s name=%s source_uri=%s",
                stamped.dataset_id,
                stamped.name,
                stamped.source_uri,
            )
            return result

    def unregister(self, dataset_id: DatasetId) -> bool:
        """Remove a dataset from the registry.

        Returns ``True`` when a dataset was removed, ``False`` when
        no dataset was registered under ``dataset_id``. The
        corresponding entry in the runtime store is also removed
        so the two registries stay in sync.
        """
        with self._lock:
            removed_result = self._results.pop(dataset_id, None) is not None
            removed_handle = self._handles.pop(dataset_id, None) is not None
            self._runtime_store.unregister(dataset_id)
            if removed_result or removed_handle:
                _LOGGER.info("Unregistered dataset: id=%s", dataset_id)
            return removed_result or removed_handle

    def reset(self) -> None:
        """Clear the registry and the underlying runtime store.

        Intended for tests; production code should rarely need
        this. The runtime store is cleared so the two registries
        stay in sync.
        """
        with self._lock:
            self._results.clear()
            self._handles.clear()
            self._runtime_store.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _stamp_handle(self, handle: DatasetHandle) -> DatasetHandle:
        """Return a copy of ``handle`` with ``registered_at`` filled in.

        Handles that already carry a timezone-aware
        ``registered_at`` are returned unchanged so callers can
        back-fill historical runs without the registry overwriting
        their timestamps.
        """
        if handle.registered_at is not None:
            return handle
        stamped_at = self._clock()
        return handle.model_copy(update={"registered_at": stamped_at})

    def _build_result(
        self,
        *,
        handle: DatasetHandle,
        ingestion: IngestionReport,
        artifact_id: ArtifactId | None,
        lineage_id: LineageId | None,
        run_id: Any,
        stage_id: Any,
    ) -> RegisteredDatasetResult:
        """Assemble a :class:`RegisteredDatasetResult` from a handle.

        ``ingestion`` is required because the
        :class:`RegisteredDatasetResult` contract requires a
        non-null :class:`IngestionReport`. Callers that do not have
        one must build a minimal :class:`IngestionReport` (or use
        :func:`register_load_result`).
        """
        return RegisteredDatasetResult(
            handle=handle,
            status=ExecutionStatus.SUCCEEDED,
            ingestion=ingestion,
            lineage_id=lineage_id,
            artifact_id=artifact_id,
            run_id=run_id,
            stage_id=stage_id,
            metadata=None,
        )

    def _build_load_lineage(
        self,
        handle: DatasetHandle,
        result: RegisteredDatasetResult,
    ) -> LineageRecord:
        """Build a ``LOAD`` :class:`LineageRecord` for a registration.

        The recorded transformation references the producing run /
        stage locators when the caller supplied them via the
        handle's ``run_id`` / ``stage_id``. The derived dataset
        ref points back at the registered handle so downstream
        consumers can chain records without a separate lookup.
        """
        fingerprint = (
            handle.fingerprint.content_hash if handle.fingerprint is not None else None
        )
        source = SourceDatasetRef(
            dataset_id=handle.dataset_id,
            dataset_ref=handle.dataset_ref,
            fingerprint=fingerprint,
            role=None,
            metadata=None,
        )
        transformation = TransformationRef(
            transformation_id=self._id_factory(),
            operation=LineageOperationType.LOAD,
            code=None,
            stage_id=handle.stage_id,
            run_id=handle.run_id,
            parameters_fingerprint=None,
            metadata=None,
        )
        derived = DerivedDatasetRef(
            dataset_id=handle.dataset_id,
            dataset_ref=handle.dataset_ref,
            fingerprint=fingerprint,
            produced_by_lineage_id=None,
            metadata=None,
        )
        return LineageRecord(
            lineage_id=LineageId(self._id_factory()),
            operation=LineageOperationType.LOAD,
            sources=(source,),
            transformation=transformation,
            derived=derived,
            recorded_at=self._clock(),
            run_id=handle.run_id,
            stage_id=handle.stage_id,
            notes=None,
            issues=(),
            warnings=(),
            metadata=None,
        )


# Module-level singleton registry. Tests that need a clean state
# should call :meth:`DatasetRegistry.reset` rather than re-binding
# the module attribute.
_REGISTRY = DatasetRegistry()


def get_dataset_registry() -> DatasetRegistry:
    """Return the module-level singleton :class:`DatasetRegistry`."""
    return _REGISTRY


def register_load_result(
    load_result: DatasetLoadResult,
    *,
    artifact_id: ArtifactId | None = None,
    registry: DatasetRegistry | None = None,
) -> RegistrationOutcome:
    """Register a :class:`DatasetLoadResult` and produce a :class:`RegistrationOutcome`.

    The convenience helper threads the
    :class:`DatasetLoadResult.handle` into the registry, records a
    ``LOAD`` :class:`LineageRecord` when a lineage store is wired
    in, and bundles the typed outputs into a
    :class:`RegistrationOutcome` for the caller.

    The function deliberately does **not** attempt to recover from
    a failed load: if ``load_result.status`` is not ``SUCCEEDED``
    the helper raises :class:`DatasetRegistryError` with code
    ``DATASET_LOAD_NOT_SUCCEEDED`` so callers do not silently
    register a broken dataset.
    """
    reg = registry if registry is not None else _REGISTRY
    if load_result.status is not ExecutionStatus.SUCCEEDED:
        raise DatasetRegistryError(
            _make_issue(
                code="DATASET_LOAD_NOT_SUCCEEDED",
                message=(
                    f"Cannot register load result with status={load_result.status!r} "
                    f"for dataset_id={(load_result.handle.dataset_id if load_result.handle else None)!r}"
                ),
            )
        )
    if load_result.handle is None:
        raise DatasetRegistryError(
            _make_issue(
                code="DATASET_LOAD_NO_HANDLE",
                message=(
                    "Cannot register load result with status=SUCCEEDED but no handle."
                ),
            )
        )
    result = reg.register(
        load_result.handle,
        artifact_id=artifact_id,
        ingestion=load_result.ingestion,
        run_id=load_result.run_id,
        stage_id=load_result.stage_id,
    )
    lineage_record: LineageRecord | None = None
    if reg._lineage_store is not None and result.lineage_id is not None:  # noqa: SLF001
        # Fetch the just-appended record by id; this preserves a
        # caller-visible reference to the lineage record produced
        # by the registration without re-walking the store.
        lineage_record = reg._lineage_store.try_get(result.lineage_id)  # noqa: SLF001
    return RegistrationOutcome(
        result=result,
        handle=load_result.handle,
        lineage_record=lineage_record,
    )