"""Backend registry and selection (Build Queue v2.1 Task 83).

This module is the canonical backend registry and selector for
the analytics platform. It pairs the contract family's
:class:`analytics_platform.contracts.execution.ExecutionBackend`
enum with runtime backend implementations (the :class:`PolarsBackend`
from Task 82) and exposes a typed ``select_backend`` /
``register_backend`` API.

Per the architecture-test plan (section 5), the ``backends``
module is a domain module and may import from contracts, core,
and the approved runtime libraries (Polars is approved).
Reporting and pipeline consume backends *through* this registry;
they never instantiate a backend directly.

Scope (Task 83):

- :class:`BackendRegistry`: process-wide registry of backend
  implementations keyed by :class:`BackendId`.
- :func:`register_backend`: register a backend implementation.
- :func:`unregister_backend`: remove a backend (used by tests
  and by the runtime config loader when switching backends).
- :func:`select_backend`: the canonical selector — returns the
  backend registered under ``backend_id``, or the default if
  ``backend_id`` is ``None``.
- :func:`default_backend_id`: the canonical default
  (``"polars-mvp"`` for the v1.1 MVP).
- :class:`BackendSelectionError`: typed exception carrying an
  :class:`Issue` payload when no backend matches.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.execution import BackendId, ExecutionBackend
from analytics_platform.core import (
    AnalyticsPlatformError,
    get_logger,
)

if TYPE_CHECKING:  # pragma: no cover - import-only
    from analytics_platform.backends import PolarsBackend

__all__ = [
    "BackendRegistry",
    "register_backend",
    "unregister_backend",
    "select_backend",
    "default_backend_id",
    "default_backend",
    "BackendSelectionError",
]


_LOGGER = get_logger("backends.registry")


def default_backend_id() -> BackendId:
    """Return the canonical default backend id.

    The v1.1 MVP supports a single in-process Polars backend.
    The default id is ``"polars-mvp"``; multi-backend routing
    is deferred to later tasks.
    """
    return BackendId("polars-mvp")


class BackendSelectionError(AnalyticsPlatformError):
    """A typed backend-selection failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class BackendRegistry:
    """A process-wide registry of backend implementations.

    The registry maps :class:`BackendId` to backend
    implementations. Access is guarded by a single lock so the
    registry is safe to mutate from concurrent threads; the
    MVP does not need cross-process backend routing.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._backends: dict[BackendId, "PolarsBackend"] = {}

    def register(self, backend: "PolarsBackend") -> None:
        """Register a backend implementation under its
        :attr:`backend.backend_id`.
        """
        with self._lock:
            self._backends[backend.backend_id] = backend
            _LOGGER.info(
                "Registered backend: id=%s runtime=%s",
                backend.backend_id,
                backend.backend_enum.value,
            )

    def unregister(self, backend_id: BackendId) -> None:
        """Remove a backend from the registry.

        A missing id is a no-op (the registry treats unregister
        of a never-registered id as a successful idempotent
        operation; use :meth:`get` if you need to detect
        presence).
        """
        with self._lock:
            self._backends.pop(backend_id, None)
            _LOGGER.info("Unregistered backend: id=%s", backend_id)

    def get(self, backend_id: BackendId) -> "PolarsBackend | None":
        """Return the backend registered under ``backend_id``,
        or ``None`` when no such backend is registered.
        """
        with self._lock:
            return self._backends.get(backend_id)

    def known(self) -> list[BackendId]:
        """Return the sorted list of registered backend ids."""
        with self._lock:
            return sorted(self._backends)

    def clear(self) -> None:
        """Remove every backend from the registry.

        Intended for tests; production code should rarely need
        this. The MVP single-backend shape means there is at
        most one id to clear in normal use.
        """
        with self._lock:
            self._backends.clear()


# Module-level singleton registry. Tests that need a clean
# state should call :meth:`BackendRegistry.clear` rather than
# patching the module attribute.
_REGISTRY = BackendRegistry()


def register_backend(backend: "PolarsBackend") -> None:
    """Register a backend implementation in the global registry."""
    _REGISTRY.register(backend)


def unregister_backend(backend_id: BackendId) -> None:
    """Remove a backend from the global registry."""
    _REGISTRY.unregister(backend_id)


def select_backend(
    backend_id: BackendId | None = None,
) -> "PolarsBackend":
    """Select a backend from the global registry.

    When ``backend_id`` is ``None``, the canonical default is
    selected. The function raises :class:`BackendSelectionError`
    when no backend matches the requested id.
    """
    target = backend_id or default_backend_id()
    backend = _REGISTRY.get(target)
    if backend is None:
        raise BackendSelectionError(
            Issue(
                code="BACKEND_NOT_REGISTERED",
                severity=Severity.ERROR,
                message=(
                    f"No backend registered for backend_id={target!r}; known={_REGISTRY.known()}"
                ),
            )
        )
    return backend


def default_backend() -> "PolarsBackend":
    """Return the canonical default backend, registering it on
    demand when the registry is empty.

    The on-demand registration is what the runtime config
    loader and the CLI rely on: callers do not need to
    explicitly register a backend before the first call.
    """
    backend = _REGISTRY.get(default_backend_id())
    if backend is not None:
        return backend
    # Lazy import to avoid pulling Polars at module load time.
    from analytics_platform.backends import PolarsBackend

    backend = PolarsBackend.from_config(default_backend_id())
    _REGISTRY.register(backend)
    return backend
