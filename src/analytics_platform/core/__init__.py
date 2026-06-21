"""Core errors and logging (Build Queue v2.1 Task 77).

This module is the canonical minimal core infrastructure for the
analytics platform:

- :class:`AnalyticsPlatformError` is the base exception for the
  platform. Every other domain exception inherits from it.
- :class:`StageError` is the typed exception for a single stage
  failure; it carries the stage id, the run id, and a typed
  :class:`Issue` payload.
- :class:`ContractError` is the typed contract validation failure
  exception.
- :class:`LimitExceeded` is the typed exception raised by the
  execution-limits policy enforcement (see ``core.limits``).
- :func:`get_logger` returns a project-wide structured logger
  that downstream modules reuse. Logging is intentionally minimal
  at the v1.1 MVP layer: domain modules may add their own
  loggers, but every module that logs must call
  :func:`get_logger` so log records carry the ``analytics_platform``
  namespace.

Per the architecture-test plan (section 3.1), ``core`` may
import from ``contracts`` only. The module uses standard
library only (``logging`` + ``typing``); it never imports
heavy compute libraries or other domain modules.

Scope (Task 77):

- ``AnalyticsPlatformError`` (base).
- ``StageError`` (typed stage failure with ``Issue``).
- ``ContractError`` (typed contract validation failure).
- ``LimitExceeded`` (typed execution-limit policy failure).
- ``get_logger`` (project-wide logger factory).
- ``configure_logging`` (idempotent root-logger setup).
- ``log_stage_failure`` (structured warning emission).
"""

from __future__ import annotations

import logging
from typing import Any

from analytics_platform.contracts.common import Issue, RunId, StageId

__all__ = [
    "AnalyticsPlatformError",
    "StageError",
    "ContractError",
    "LimitExceeded",
    "get_logger",
    "configure_logging",
    "log_stage_failure",
]


# Project-wide logger namespace. Downstream modules obtain a
# child logger via ``get_logger(__name__)`` so records carry
# the ``analytics_platform.`` prefix and can be filtered as a
# group.
_LOGGER_NAMESPACE = "analytics_platform"


class AnalyticsPlatformError(Exception):
    """Base exception for the analytics platform.

    Every other domain exception in the analytics platform
    inherits from :class:`AnalyticsPlatformError`. Catching this
    base class catches the entire platform's error surface; catch
    a more specific subclass when you need to recover from a
    specific kind of failure (e.g. ``StageError``).
    """

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, str] = dict(context) if context else {}


class StageError(AnalyticsPlatformError):
    """A typed exception for a single stage failure.

    ``StageError`` carries the :class:`Issue` payload so callers
    can introspect the failure without parsing the message.
    Optional ``stage_id`` and ``run_id`` locators are recorded for
    log correlation.
    """

    def __init__(
        self,
        message: str,
        *,
        issue: Issue,
        stage_id: StageId | None = None,
        run_id: RunId | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.issue = issue
        self.stage_id = stage_id
        self.run_id = run_id


class ContractError(AnalyticsPlatformError):
    """A typed exception for a contract validation failure.

    ``ContractError`` is raised by the core runtime when a
    contract is constructed with values that fail an invariant
    or when an adapter attempts to bridge two contracts in a way
    the contracts do not support. The exception carries the
    :class:`Issue` payload so the failure is consumable by
    reporting and registry.
    """

    def __init__(
        self,
        message: str,
        *,
        issue: Issue,
        context: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.issue = issue


class LimitExceeded(AnalyticsPlatformError):
    """A typed exception raised when an execution-limit policy
    check fails.

    ``LimitExceeded`` carries the :class:`Issue` payload so
    reporting / registry can group failures on the stable issue
    ``code``. The check functions in ``core.limits`` are the
    canonical way to raise this exception; downstream callers
    should not construct it directly.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a project-wide logger.

    The returned logger is a child of the
    ``analytics_platform`` namespace so records can be filtered
    together. ``name`` is the typical ``__name__`` of the calling
    module; ``None`` returns the root ``analytics_platform``
    logger.
    """
    if name is None:
        return logging.getLogger(_LOGGER_NAMESPACE)
    if name == _LOGGER_NAMESPACE or name.startswith(_LOGGER_NAMESPACE + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the project-wide root logger once.

    Idempotent: a second call with the same level is a no-op.
    The function exists so that the CLI can wire up a single
    handler at startup without forcing every module to know how
    the project formats log records.
    """
    root = logging.getLogger(_LOGGER_NAMESPACE)
    if root.handlers:
        for handler in list(root.handlers):
            root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)


def log_stage_failure(logger: logging.Logger, exc: StageError) -> None:
    """Emit a structured warning when a stage fails.

    The function records the stage id, the run id, the issue
    code / severity / message, and any context. The intent is to
    give downstream observers (log aggregators, CI, reporting) a
    consistent shape for stage failures without forcing every
    caller to format the message by hand.
    """
    extras: dict[str, Any] = {
        "stage_id": exc.stage_id,
        "run_id": exc.run_id,
        "issue_code": exc.issue.code,
        "issue_severity": exc.issue.severity,
        "issue_message": exc.issue.message,
    }
    extras.update(exc.context)
    logger.warning(
        "Stage %s failed: %s (code=%s severity=%s)",
        exc.stage_id,
        exc.issue.message,
        exc.issue.code,
        exc.issue.severity,
        extra=extras,
    )
