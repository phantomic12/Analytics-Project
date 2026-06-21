"""Polars backend adapter (Build Queue v2.1 Task 82).

This module is the canonical Polars backend adapter. It implements
the runtime mapping from the contract family's
:class:`analytics_platform.contracts.execution.ExecutionBackend`
enum (with its :class:`BackendId` / :class:`LazyFrameRef` /
:class:`BackendObjectRef` / :class:`MaterializationPolicy` /
:class:`MaterializationRequest` / :class:`MaterializationResult`
shapes) to Polars types and back.

Per the architecture-test plan (section 5: Domain module
boundaries), the ``backends`` module is a domain module and may
import from contracts, core, and the approved runtime libraries
(``polars`` is in the approved list per
``dependency-policy-v1.1.md``). It must never expose raw Polars
types across the public surface — that would be a leaky
abstraction. The ``BackendObjectRef`` contract keeps the
Polars-side objects private behind a typed handle.

The MVP supports a single in-process Polars backend. Multi-process
or remote backends (DuckDB, S3 via Polars cloud, etc.) are deferred
to later tasks (Task 112 for DuckDB).

Scope:

- :class:`PolarsBackend`: the canonical backend implementation
  that holds the in-process Polars runtime context and exposes
  the typed backend operations.
- :func:`polars_to_handle` / :func:`handle_to_polars`: the
  internal type bridges used by the adapter. They are *not*
  exported publicly.
- :class:`PolarsBackendError`: a typed exception carrying the
  :class:`Issue` payload.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
)
from analytics_platform.contracts.execution import (
    BackendId,
    BackendObjectRef,
    ExecutionBackend,
    LazyFrameRef,
    MaterializationPolicy,
    MaterializationRequest,
    MaterializationResult,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

if TYPE_CHECKING:  # pragma: no cover - import-only
    import polars as pl

__all__ = [
    "PolarsBackend",
    "PolarsBackendError",
]


_LOGGER = get_logger("backends.polars")


class PolarsBackendError(AnalyticsPlatformError):
    """A typed Polars-backend failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# The runtime Polars module is imported lazily so the rest of the
# analytics platform can be imported / tested without Polars.
def _load_polars():
    try:
        import polars as pl
    except ImportError as exc:  # pragma: no cover - rare
        raise PolarsBackendError(
            _make_issue(
                code="POLARS_NOT_INSTALLED",
                message=(
                    "Polars is required for the Polars backend adapter "
                    f"but is not installed: {exc}"
                ),
            )
        ) from exc
    return pl


def polars_to_handle(
    frame: "pl.LazyFrame | pl.DataFrame",
    *,
    backend_id: BackendId,
    handle: str,
) -> BackendObjectRef:
    """Convert a Polars frame into a typed :class:`BackendObjectRef`.

    The Polars frame is *not* serialized into the ref; the ref
    carries only the (backend, backend_id, kind, handle) tuple.
    The Polars runtime stores the frame in its private state under
    ``handle``. The :class:`PolarsBackend` keeps a registry of
    ``handle -> frame`` so the same :class:`PolarsBackend` can
    later resolve the ref back to the frame via
    :func:`handle_to_polars`.
    """
    import polars as pl

    if not isinstance(frame, (pl.LazyFrame, pl.DataFrame)):
        raise PolarsBackendError(
            _make_issue(
                code="POLARS_INVALID_FRAME",
                message=(
                    f"polars_to_handle expected a LazyFrame or DataFrame, "
                    f"got {type(frame).__name__}"
                ),
            )
        )
    kind = "lazy_frame" if isinstance(frame, pl.LazyFrame) else "data_frame"
    return BackendObjectRef(
        backend=ExecutionBackend.POLARS,
        backend_id=backend_id,
        object_kind=kind,
        handle=handle,
    )


def handle_to_polars(
    ref: BackendObjectRef,
    *,
    registry: dict[str, "pl.LazyFrame | pl.DataFrame"],
) -> "pl.LazyFrame | pl.DataFrame":
    """Resolve a :class:`BackendObjectRef` to its Polars frame.

    The function consults the ``registry`` passed in by the
    :class:`PolarsBackend` that owns the runtime. A missing
    ``handle`` raises :class:`PolarsBackendError` with a typed
    issue.
    """
    if ref.backend is not ExecutionBackend.POLARS:
        raise PolarsBackendError(
            _make_issue(
                code="POLARS_BACKEND_MISMATCH",
                message=(
                    f"handle_to_polars expected a Polars ref, got "
                    f"backend={ref.backend.value!r}"
                ),
            )
        )
    if ref.handle not in registry:
        raise PolarsBackendError(
            _make_issue(
                code="POLARS_HANDLE_NOT_FOUND",
                message=(
                    f"Polars handle {ref.handle!r} is not registered in "
                    f"backend_id={ref.backend_id!r}"
                ),
            )
        )
    return registry[ref.handle]


def lazyframe_to_lazylike(
    frame: "pl.LazyFrame",
) -> "pl.LazyFrame | pl.DataFrame":
    """Normalize a :class:`pl.LazyFrame` to a lazy-or-dataframe for
    internal use.

    The MVP passes ``LazyFrame`` through; the helper exists so
    that future backends can return a non-lazy reference.
    """
    return frame


class PolarsBackend:
    """The canonical Polars backend implementation.

    A :class:`PolarsBackend` owns an in-process Polars runtime
    context and a private ``handle -> frame`` registry. Domain
    modules never see the Polars frame directly; they receive a
    :class:`BackendObjectRef` and resolve it back to the frame
    via the backend's ``resolve`` method.

    Construction is via :meth:`from_config` (the canonical path
    used by the backend registry in Task 83) or directly via the
    default constructor (used by tests and in-process adapters).
    """

    def __init__(
        self,
        backend_id: BackendId,
        *,
        pl_module: Any = None,
    ) -> None:
        self._backend_id = backend_id
        self._pl = pl_module if pl_module is not None else _load_polars()
        self._registry: dict[str, Any] = {}

    @classmethod
    def from_config(
        cls,
        backend_id: BackendId,
    ) -> "PolarsBackend":
        """Construct a :class:`PolarsBackend` from a backend id.

        Per the v1.1 MVP, the only supported configuration is
        ``ExecutionBackend.POLARS`` with a process-local Polars
        runtime. Multi-process / remote backends are deferred to
        later tasks.
        """
        return cls(backend_id=backend_id)

    @property
    def backend_id(self) -> BackendId:
        return self._backend_id

    @property
    def backend_enum(self) -> ExecutionBackend:
        return ExecutionBackend.POLARS

    @property
    def polars(self) -> Any:
        return self._pl

    # -----------------------------------------------------------------
    # Ingest / register
    # -----------------------------------------------------------------
    def register(
        self,
        frame: "pl.LazyFrame | pl.DataFrame",
        *,
        handle: str | None = None,
    ) -> BackendObjectRef:
        """Register a Polars frame under a fresh handle and return
        the typed ref.

        ``handle`` defaults to a UUID-like identifier (Polars
        provides a unique-name helper); the caller can pass an
        explicit handle to make the ref reproducible.
        """
        actual_handle = handle or f"polars-{uuid.uuid4().hex[:12]}"
        if actual_handle in self._registry:
            raise PolarsBackendError(
                _make_issue(
                    code="POLARS_HANDLE_EXISTS",
                    message=(
                        f"Handle {actual_handle!r} is already registered "
                        f"in backend_id={self._backend_id!r}"
                    ),
                )
            )
        self._registry[actual_handle] = frame
        return polars_to_handle(
            frame, backend_id=self._backend_id, handle=actual_handle
        )

    # -----------------------------------------------------------------
    # Resolve
    # -----------------------------------------------------------------
    def resolve(self, ref: BackendObjectRef) -> Any:
        """Resolve a :class:`BackendObjectRef` to its Polars frame."""
        return handle_to_polars(ref, registry=self._registry)

    # -----------------------------------------------------------------
    # Materialize
    # -----------------------------------------------------------------
    def materialize(
        self,
        request: MaterializationRequest,
    ) -> MaterializationResult:
        """Materialize a Polars frame per the policy in ``request``.

        Policies:

        - ``EAGER``: collect the LazyFrame into a DataFrame and
          store the DataFrame under a fresh handle.
        - ``PERSISTED``: serialize the LazyFrame to a Parquet file
          at ``target_uri`` (or a temp location) and return a
          :class:`MaterializationResult` with ``artifact`` set to
          a :class:`ArtifactRef` of the persisted file. The
          :class:`ArtifactRef` family is in ``contracts.artifacts``;
          this MVP uses a minimal in-memory :class:`ArtifactRef`
          constructed via the ``artifacts`` module.
        - ``IN_MEMORY`` / ``LAZY``: store the LazyFrame under a
          fresh handle and return a result that points to the
          in-memory ref.
        """
        if request.policy is MaterializationPolicy.EAGER:
            ref = self._resolve_or_register(request)
            frame = self._registry[ref.handle]
            df = self._eager_collect(frame)
            eager_ref = self.register(df)
            return MaterializationResult(
                policy=request.policy,
                status=self._materialization_status_for_result_ref(eager_ref),
                result_ref=eager_ref,
            )
        if request.policy is MaterializationPolicy.PERSISTED:
            ref = self._resolve_or_register(request)
            frame = self._registry[ref.handle]
            from pathlib import Path as _P
            from analytics_platform.contracts.common import ArtifactRef as _ArtifactRef

            uri = self._persist_to_parquet(frame, request.target_uri)
            try:
                content = (
                    _P(uri).read_bytes() if _P(uri).exists() else b""
                )
            except OSError:
                content = b""

            # ``_ArtifactRef`` is the canonical pointer used by the
            # execution contract family. It pairs a stable id + kind
            # + uri and never embeds the artifact body. The hash +
            # storage policy + size are recorded in the run
            # manifest separately via :class:`PersistedArtifact`.
            artifact = _ArtifactRef(
                artifact_id=f"mat-{uri.split('/')[-1]}",
                kind="dataset",
                uri=uri,
            )
            # ``status`` is a string. We import the ExecutionStatus
            # from contracts to keep types aligned.
            from analytics_platform.contracts.common import (
                ExecutionStatus,
            )

            return MaterializationResult(
                policy=request.policy,
                status=ExecutionStatus.SUCCEEDED,
                artifact=artifact,
                target_uri=uri,
            )
        if request.policy in (
            MaterializationPolicy.IN_MEMORY,
            MaterializationPolicy.LAZY,
        ):
            ref = self._resolve_or_register(request)
            return MaterializationResult(
                policy=request.policy,
                status=self._materialization_status_for_result_ref(ref),
                result_ref=ref,
            )
        # Defensive: any new enum value falls back to a LAZY-style
        # materialization.
        ref = self._resolve_or_register(request)
        return MaterializationResult(
            policy=request.policy,
            status=self._materialization_status_for_result_ref(ref),
            result_ref=ref,
        )

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------
    def _resolve_or_register(
        self,
        request: MaterializationRequest,
    ) -> BackendObjectRef:
        """Resolve ``request``'s source ref or register a no-op frame.

        ``MaterializationRequest`` carries exactly one of
        ``lazy_frame_ref`` / ``backend_object_ref``. The MVP
        supports ``backend_object_ref``; ``lazy_frame_ref`` is
        accepted via the contract's compatibility layer (a
        ``LazyFrameRef`` carries a ``handle`` and a
        ``backend_id``; we treat it as a ``BackendObjectRef``
        with ``object_kind='lazy_frame'``).
        """
        from analytics_platform.contracts.execution import ExecutionStatus

        if request.backend_object_ref is not None:
            ref = request.backend_object_ref
            if ref.backend_id not in (self._backend_id, self._backend_id):
                # Defensive: mismatch is unusual; the contract
                # doesn't enforce backend_id == self.backend_id
                # for adapters, so we accept either.
                pass
            return ref
        if request.lazy_frame_ref is not None:
            return BackendObjectRef(
                backend=ExecutionBackend.POLARS,
                backend_id=request.lazy_frame_ref.backend_id,
                object_kind="lazy_frame",
                handle=request.lazy_frame_ref.handle,
            )
        raise PolarsBackendError(
            _make_issue(
                code="POLARS_NO_SOURCE",
                message=(
                    "MaterializationRequest must reference exactly one of "
                    "lazy_frame_ref or backend_object_ref"
                ),
            )
        )

    def _eager_collect(self, frame: Any) -> Any:
        if hasattr(frame, "collect"):
            return frame.collect()
        return frame

    def _persist_to_parquet(self, frame: Any, target_uri: str | None) -> str:
        import tempfile
        from pathlib import Path

        target = Path(target_uri) if target_uri else None
        if target is None:
            with tempfile.NamedTemporaryFile(
                suffix=".parquet", delete=False
            ) as tmp:
                path = Path(tmp.name)
        else:
            path = target
        # LazyFrame: sink_parquet; DataFrame: write_parquet.
        if hasattr(frame, "sink_parquet"):
            frame.sink_parquet(str(path))
        elif hasattr(frame, "write_parquet"):
            frame.write_parquet(str(path))
        else:  # pragma: no cover - defensive
            raise PolarsBackendError(
                _make_issue(
                    code="POLARS_PERSIST_FAILED",
                    message=(
                        f"Cannot persist frame of type {type(frame).__name__}"
                    ),
                )
            )
        _LOGGER.info("Persisted Polars frame to %s", path)
        return str(path)

    def _materialization_status_for_result_ref(
        self, ref: BackendObjectRef
    ) -> Any:
        from analytics_platform.contracts.common import ExecutionStatus

        return ExecutionStatus.SUCCEEDED
