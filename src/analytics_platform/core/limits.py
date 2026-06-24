"""Execution limits policy enforcement (Build Queue v2.1 Task 79).

This module is the canonical runtime enforcement of
:class:`analytics_platform.contracts.execution.ExecutionLimitPolicy`.
The contract family defines the *shape* of an execution limit
policy; this module implements the runtime *checks*:

- :class:`LimitExceeded` is the typed exception raised when a
  limit is breached. It carries the :class:`Issue` payload so
  failures are consumable by reporting and registry.
- :func:`check_row_count` validates that a row count is within
  the policy's row budget.
- :func:`check_column_count` validates a column count.
- :func:`check_collect_allowed` validates that the collect
  policy allows the requested collect mode.
- :func:`check_pandas_conversion_allowed` validates that pandas
  conversion is allowed under the policy.
- :func:`check_artifact_size` validates that an artifact size is
  within the per-run artifact budget.

The module uses standard library only; it never imports heavy
compute libraries or other domain modules. Per the
architecture-test plan (section 3.1), ``core`` may import from
``contracts`` only.
"""

from __future__ import annotations

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
)
from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)

from analytics_platform.core import LimitExceeded  # re-export

__all__ = [
    "LimitExceeded",
    "check_row_count",
    "check_column_count",
    "check_collect_allowed",
    "check_pandas_conversion_allowed",
    "check_artifact_size",
    "is_collect_allowed",
    "is_pandas_conversion_allowed",
]


# Canonical issue codes for the limit-enforcement surface. They
# are stable strings so reporting / registry can group on them.
class LimitCode:
    """Stable machine-readable codes for execution-limit failures."""

    ROW_LIMIT_EXCEEDED = "ROW_LIMIT_EXCEEDED"
    COLUMN_LIMIT_EXCEEDED = "COLUMN_LIMIT_EXCEEDED"
    COLLECT_FORBIDDEN = "COLLECT_FORBIDDEN"
    COLLECT_ROW_LIMIT_EXCEEDED = "COLLECT_ROW_LIMIT_EXCEEDED"
    PANDAS_CONVERSION_FORBIDDEN = "PANDAS_CONVERSION_FORBIDDEN"
    PANDAS_CONVERSION_ROW_LIMIT_EXCEEDED = "PANDAS_CONVERSION_ROW_LIMIT_EXCEEDED"
    ARTIFACT_SIZE_EXCEEDED = "ARTIFACT_SIZE_EXCEEDED"


def _make_issue(
    code: str,
    message: str,
    severity: Severity = Severity.ERROR,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> Issue:
    return Issue(
        code=code,
        severity=severity,
        message=message,
        stage_id=stage_id,
        run_id=run_id,
    )


def check_row_count(
    policy: ExecutionLimitPolicy,
    *,
    row_count: int,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> None:
    """Raise :class:`LimitExceeded` if ``row_count`` is invalid for
    the policy.

    Per the contract, ``ExecutionLimitPolicy`` does not expose a
    top-level ``max_rows`` field; the row budget lives on the
    :class:`CollectPolicy` and :class:`PandasConversionPolicy`
    components. This function is a *sanity* check: it rejects
    negative row counts unconditionally. The actual per-operation
    enforcement happens in :func:`check_collect_allowed` and
    :func:`check_pandas_conversion_allowed`.
    """
    if row_count < 0:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.ROW_LIMIT_EXCEEDED,
                message=(f"row_count={row_count} is negative"),
                stage_id=stage_id,
                run_id=run_id,
            )
        )


def check_column_count(
    policy: ExecutionLimitPolicy,
    *,
    column_count: int,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> None:
    """Raise :class:`LimitExceeded` if ``column_count`` is invalid
    for the policy.

    The contract's :class:`ExecutionLimitPolicy` does not expose a
    top-level ``max_columns`` field. This function is a *sanity*
    check: it rejects negative column counts unconditionally.
    Per-stage column-count enforcement happens at the
    backend-specific layer (e.g. Polars / DuckDB adapters).
    """
    if column_count < 0:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.COLUMN_LIMIT_EXCEEDED,
                message=(f"column_count={column_count} is negative"),
                stage_id=stage_id,
                run_id=run_id,
            )
        )


def is_collect_allowed(policy: CollectPolicy) -> bool:
    """Return True if the policy permits a non-trivial collect.

    ``BOUNDED`` collect is allowed only when explicit limits are
    present; ``FORBIDDEN`` collect is never allowed.
    """
    if policy.mode is CollectMode.FORBIDDEN:
        return False
    # BOUNDED + non-positive max_rows is treated as forbidden; any
    # future enum values are also forbidden by default.
    if policy.mode is CollectMode.BOUNDED:
        return policy.max_rows is not None and policy.max_rows > 0
    return False  # type: ignore[unreachable]


def is_pandas_conversion_allowed(policy: PandasConversionPolicy) -> bool:
    """Return True if the policy permits a non-trivial pandas conversion.

    ``BOUNDED`` conversion is allowed only when explicit limits are
    present; ``FORBIDDEN`` conversion is never allowed.
    """
    if policy.mode is PandasConversionMode.FORBIDDEN:
        return False
    if policy.mode is PandasConversionMode.BOUNDED:
        return policy.max_rows is not None and policy.max_rows > 0
    return False  # type: ignore[unreachable]


def check_collect_allowed(
    policy: CollectPolicy,
    *,
    row_count: int,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> None:
    """Raise :class:`LimitExceeded` if the collect is forbidden
    or the requested row count would breach the bounded limit.
    """
    if policy.mode is CollectMode.FORBIDDEN:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.COLLECT_FORBIDDEN,
                message=("Collect is forbidden by ExecutionLimitPolicy."),
                stage_id=stage_id,
                run_id=run_id,
            )
        )
    if policy.mode is CollectMode.BOUNDED:
        if policy.max_rows is None or policy.max_rows <= 0:
            raise LimitExceeded(
                _make_issue(
                    code=LimitCode.COLLECT_ROW_LIMIT_EXCEEDED,
                    message=("Collect is BOUNDED but max_rows is not set or is zero."),
                    stage_id=stage_id,
                    run_id=run_id,
                )
            )
        if row_count > policy.max_rows:
            raise LimitExceeded(
                _make_issue(
                    code=LimitCode.COLLECT_ROW_LIMIT_EXCEEDED,
                    message=(
                        f"Requested collect of {row_count} rows exceeds "
                        f"policy max_rows={policy.max_rows}."
                    ),
                    stage_id=stage_id,
                    run_id=run_id,
                )
            )


def check_pandas_conversion_allowed(
    policy: PandasConversionPolicy,
    *,
    row_count: int,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> None:
    """Raise :class:`LimitExceeded` if pandas conversion is
    forbidden or the requested row count would breach the bounded
    limit.
    """
    if policy.mode is PandasConversionMode.FORBIDDEN:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.PANDAS_CONVERSION_FORBIDDEN,
                message=("Pandas conversion is forbidden by ExecutionLimitPolicy."),
                stage_id=stage_id,
                run_id=run_id,
            )
        )
    if policy.mode is PandasConversionMode.BOUNDED:
        if policy.max_rows is None or policy.max_rows <= 0:
            raise LimitExceeded(
                _make_issue(
                    code=LimitCode.PANDAS_CONVERSION_ROW_LIMIT_EXCEEDED,
                    message=("Pandas conversion is BOUNDED but max_rows is not set or is zero."),
                    stage_id=stage_id,
                    run_id=run_id,
                )
            )
        if row_count > policy.max_rows:
            raise LimitExceeded(
                _make_issue(
                    code=LimitCode.PANDAS_CONVERSION_ROW_LIMIT_EXCEEDED,
                    message=(
                        f"Requested pandas conversion of {row_count} rows "
                        f"exceeds policy max_rows={policy.max_rows}."
                    ),
                    stage_id=stage_id,
                    run_id=run_id,
                )
            )


def check_artifact_size(
    policy: ExecutionLimitPolicy,
    *,
    size_bytes: int,
    max_artifact_bytes: int = 0,
    stage_id: StageId | None = None,
    run_id: RunId | None = None,
) -> None:
    """Raise :class:`LimitExceeded` if ``size_bytes`` exceeds
    ``max_artifact_bytes`` (per-run override) or, when the
    override is 0, the policy's per-artifact budget
    (``policy.memory_budget.max_bytes``).
    """
    if size_bytes < 0:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.ARTIFACT_SIZE_EXCEEDED,
                message=(f"size_bytes={size_bytes} is negative"),
                stage_id=stage_id,
                run_id=run_id,
            )
        )
    if max_artifact_bytes > 0:
        if size_bytes > max_artifact_bytes:
            raise LimitExceeded(
                _make_issue(
                    code=LimitCode.ARTIFACT_SIZE_EXCEEDED,
                    message=(
                        f"size_bytes={size_bytes} exceeds per-run "
                        f"max_artifact_bytes={max_artifact_bytes}"
                    ),
                    stage_id=stage_id,
                    run_id=run_id,
                )
            )
        return
    # No per-run override: fall back to the policy's memory
    # budget as the artifact-size budget.
    budget = policy.memory_budget.max_bytes
    if budget > 0 and size_bytes > budget:
        raise LimitExceeded(
            _make_issue(
                code=LimitCode.ARTIFACT_SIZE_EXCEEDED,
                message=(f"size_bytes={size_bytes} exceeds policy memory_budget={budget}"),
                stage_id=stage_id,
                run_id=run_id,
            )
        )
