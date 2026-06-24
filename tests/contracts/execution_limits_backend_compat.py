"""Compatibility adapter: Execution-limits -> Backend (Task 49).

Per the architecture-test plan, the execution-limit policy is the
canonical way a backend is told how to bound its work. This module
is the test-only compatibility helper used by
``tests/contracts/test_compatibility_47_to_50.py`` to verify the
shape transition.
"""

from __future__ import annotations

from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    MaterializationPolicy,
    MaterializationRequest,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)


class ExecutionLimitsToBackendAdapter:
    """Adapter: backend knobs -> an ``ExecutionLimitPolicy`` that
    drives every backend family request shape.

    The adapter is intentionally minimal: a backend exposes its
    internal knobs (row / column / byte budgets), and the adapter
    builds a typed policy that the rest of the platform can
    consume uniformly.
    """

    @staticmethod
    def from_backend_knobs(
        *,
        max_rows: int,
        max_columns: int | None = None,
        max_bytes: int,
    ) -> ExecutionLimitPolicy:
        """Build a policy from a backend's row / column / byte knobs.

        Parameters
        ----------
        max_rows:
            Non-negative row budget.
        max_columns:
            Optional non-negative column budget.
        max_bytes:
            Non-negative memory budget in bytes.
        """
        if max_rows < 0:
            raise ValueError("max_rows must be >= 0")
        if max_bytes < 0:
            raise ValueError("max_bytes must be >= 0")
        if max_columns is not None and max_columns < 0:
            raise ValueError("max_columns must be >= 0")

        collect = CollectPolicy(mode=CollectMode.BOUNDED, max_rows=max_rows)
        pandas = PandasConversionPolicy(
            mode=PandasConversionMode.BOUNDED, max_rows=max_rows
        )
        memory = MemoryBudgetPolicy(max_bytes=max_bytes)
        return ExecutionLimitPolicy(
            collect=collect,
            pandas_conversion=pandas,
            memory_budget=memory,
        )

    @staticmethod
    def build_materialization_request(
        *,
        policy: MaterializationPolicy,
        execution_limits: ExecutionLimitPolicy,
    ) -> MaterializationRequest:
        """Build a :class:`MaterializationRequest` that carries the
        given execution limits into the backend.
        """
        return MaterializationRequest(
            policy=policy,
            execution_limits=execution_limits,
        )
