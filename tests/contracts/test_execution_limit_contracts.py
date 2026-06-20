"""Tests for execution limit contracts (Build Queue v2.1 Task 14).

Covers:

- ``CollectMode`` / ``CollectPolicy`` validation and serialization.
- ``PandasConversionMode`` / ``PandasConversionPolicy`` validation.
- ``MemoryBudgetPolicy`` validation (explicit, serializable).
- ``ExecutionLimitPolicy`` serialization round-trip and defaults.
- Unbounded collect/materialization is rejected by default (and not
  representable when ``mode=bounded`` without explicit ``max_rows``).
- Pandas conversion is explicit and bounded.
- No raw dataframe-like object fields: structural surface guards.
- Import-weight guard: no heavy compute libraries are pulled by the
  execution limit contracts module.

These tests intentionally avoid importing any heavy compute library so they
exercise the dependency-light contract surface only. They do not implement
runtime enforcement, backends, profiling, features, modeling, or
materialization behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)


# ---------------------------------------------------------------------------
# CollectMode
# ---------------------------------------------------------------------------
class TestCollectMode:
    def test_known_members(self) -> None:
        assert CollectMode.FORBIDDEN.value == "forbidden"
        assert CollectMode.BOUNDED.value == "bounded"

    def test_enum_from_value(self) -> None:
        assert CollectMode("forbidden") is CollectMode.FORBIDDEN
        assert CollectMode("bounded") is CollectMode.BOUNDED

    def test_no_unbounded_member(self) -> None:
        # Unbounded collect must not be representable.
        with pytest.raises(ValueError):
            CollectMode("unbounded")  # type: ignore[arg-type]

    def test_serializes_as_plain_string(self) -> None:
        assert CollectMode.FORBIDDEN == "forbidden"


# ---------------------------------------------------------------------------
# CollectPolicy
# ---------------------------------------------------------------------------
class TestCollectPolicy:
    def test_default_is_forbidden(self) -> None:
        p = CollectPolicy()
        assert p.mode is CollectMode.FORBIDDEN
        assert p.max_rows is None
        assert p.max_bytes is None

    def test_forbidden_with_no_limits_allowed(self) -> None:
        # FORBIDDEN does not require limits; absence of limits is fine.
        p = CollectPolicy(mode=CollectMode.FORBIDDEN)
        assert p.mode is CollectMode.FORBIDDEN

    def test_bounded_requires_max_rows(self) -> None:
        with pytest.raises(ValidationError):
            CollectPolicy(mode=CollectMode.BOUNDED)

    def test_bounded_with_max_rows(self) -> None:
        p = CollectPolicy(mode=CollectMode.BOUNDED, max_rows=1_000)
        assert p.mode is CollectMode.BOUNDED
        assert p.max_rows == 1_000
        assert p.max_bytes is None

    def test_bounded_with_rows_and_bytes(self) -> None:
        p = CollectPolicy(mode=CollectMode.BOUNDED, max_rows=1_000, max_bytes=4_096)
        assert p.max_bytes == 4_096

    def test_mode_string_coerced(self) -> None:
        p = CollectPolicy(mode="bounded", max_rows=10)  # type: ignore[arg-type]
        assert p.mode is CollectMode.BOUNDED

    def test_negative_max_rows_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CollectPolicy(mode=CollectMode.BOUNDED, max_rows=-1)

    def test_negative_max_bytes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CollectPolicy(mode=CollectMode.BOUNDED, max_rows=10, max_bytes=-1)

    def test_zero_max_rows_allowed(self) -> None:
        p = CollectPolicy(mode=CollectMode.BOUNDED, max_rows=0)
        assert p.max_rows == 0

    def test_unknown_field_rejected(self) -> None:
        # An extra field would be the natural smuggling vector for a raw
        # dataframe object. The contract must forbid it.
        with pytest.raises(ValidationError):
            CollectPolicy(  # type: ignore[call-arg]
                mode=CollectMode.BOUNDED,
                max_rows=10,
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        p = CollectPolicy(mode=CollectMode.BOUNDED, max_rows=10)
        with pytest.raises(ValidationError):
            p.max_rows = 20  # type: ignore[misc]

    def test_round_trip(self) -> None:
        p = CollectPolicy(
            mode=CollectMode.BOUNDED,
            max_rows=1_000,
            max_bytes=4_096,
            metadata={"reason": "bounded-collect"},
        )
        data = p.model_dump(mode="json")
        assert data["mode"] == "bounded"
        assert data["max_rows"] == 1_000
        restored = CollectPolicy.model_validate(data)
        assert restored == p
        assert restored.mode is CollectMode.BOUNDED


# ---------------------------------------------------------------------------
# PandasConversionMode / PandasConversionPolicy
# ---------------------------------------------------------------------------
class TestPandasConversionMode:
    def test_known_members(self) -> None:
        assert PandasConversionMode.FORBIDDEN.value == "forbidden"
        assert PandasConversionMode.BOUNDED.value == "bounded"

    def test_no_unbounded_member(self) -> None:
        with pytest.raises(ValueError):
            PandasConversionMode("unbounded")  # type: ignore[arg-type]


class TestPandasConversionPolicy:
    def test_default_is_forbidden(self) -> None:
        p = PandasConversionPolicy()
        assert p.mode is PandasConversionMode.FORBIDDEN
        assert p.max_rows is None
        assert p.max_columns is None

    def test_bounded_requires_max_rows(self) -> None:
        with pytest.raises(ValidationError):
            PandasConversionPolicy(mode=PandasConversionMode.BOUNDED)

    def test_bounded_with_max_rows(self) -> None:
        p = PandasConversionPolicy(mode=PandasConversionMode.BOUNDED, max_rows=1_000)
        assert p.mode is PandasConversionMode.BOUNDED
        assert p.max_rows == 1_000

    def test_bounded_with_optional_bounds(self) -> None:
        p = PandasConversionPolicy(
            mode=PandasConversionMode.BOUNDED,
            max_rows=1_000,
            max_bytes=4_096,
            max_columns=64,
        )
        assert p.max_bytes == 4_096
        assert p.max_columns == 64

    def test_negative_max_columns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PandasConversionPolicy(
                mode=PandasConversionMode.BOUNDED, max_rows=10, max_columns=-1
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PandasConversionPolicy(  # type: ignore[call-arg]
                mode=PandasConversionMode.BOUNDED,
                max_rows=10,
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        p = PandasConversionPolicy(mode=PandasConversionMode.BOUNDED, max_rows=10)
        with pytest.raises(ValidationError):
            p.max_rows = 20  # type: ignore[misc]

    def test_round_trip(self) -> None:
        p = PandasConversionPolicy(
            mode=PandasConversionMode.BOUNDED,
            max_rows=1_000,
            max_bytes=4_096,
            max_columns=32,
        )
        data = p.model_dump(mode="json")
        assert data["mode"] == "bounded"
        assert data["max_columns"] == 32
        restored = PandasConversionPolicy.model_validate(data)
        assert restored == p
        assert restored.mode is PandasConversionMode.BOUNDED


# ---------------------------------------------------------------------------
# MemoryBudgetPolicy
# ---------------------------------------------------------------------------
class TestMemoryBudgetPolicy:
    def test_valid_with_max_bytes(self) -> None:
        b = MemoryBudgetPolicy(max_bytes=1_073_741_824)
        assert b.max_bytes == 1_073_741_824
        assert b.scope is None

    def test_valid_with_scope(self) -> None:
        b = MemoryBudgetPolicy(max_bytes=1024, scope="stage")
        assert b.scope == "stage"

    def test_max_bytes_required(self) -> None:
        with pytest.raises(ValidationError):
            MemoryBudgetPolicy()  # type: ignore[call-arg]

    def test_negative_max_bytes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MemoryBudgetPolicy(max_bytes=-1)

    def test_zero_max_bytes_allowed(self) -> None:
        b = MemoryBudgetPolicy(max_bytes=0)
        assert b.max_bytes == 0

    def test_empty_scope_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MemoryBudgetPolicy(max_bytes=1024, scope="")

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MemoryBudgetPolicy(  # type: ignore[call-arg]
                max_bytes=1024,
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        b = MemoryBudgetPolicy(max_bytes=1024)
        with pytest.raises(ValidationError):
            b.max_bytes = 2048  # type: ignore[misc]

    def test_round_trip(self) -> None:
        b = MemoryBudgetPolicy(max_bytes=1_024, scope="run", metadata={"unit": "bytes"})
        data = b.model_dump(mode="json")
        assert data["max_bytes"] == 1_024
        assert data["scope"] == "run"
        restored = MemoryBudgetPolicy.model_validate(data)
        assert restored == b


# ---------------------------------------------------------------------------
# ExecutionLimitPolicy
# ---------------------------------------------------------------------------
class TestExecutionLimitPolicy:
    def _budget(self) -> MemoryBudgetPolicy:
        return MemoryBudgetPolicy(max_bytes=1_073_741_824, scope="stage")

    def test_defaults_are_restrictive(self) -> None:
        p = ExecutionLimitPolicy(memory_budget=self._budget())
        assert p.collect.mode is CollectMode.FORBIDDEN
        assert p.pandas_conversion.mode is PandasConversionMode.FORBIDDEN
        assert p.memory_budget.max_bytes == 1_073_741_824

    def test_memory_budget_required(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionLimitPolicy()  # type: ignore[call-arg]

    def test_explicit_bounded_collect_and_pandas(self) -> None:
        p = ExecutionLimitPolicy(
            collect=CollectPolicy(mode=CollectMode.BOUNDED, max_rows=1_000),
            pandas_conversion=PandasConversionPolicy(
                mode=PandasConversionMode.BOUNDED, max_rows=1_000, max_columns=32
            ),
            memory_budget=self._budget(),
        )
        assert p.collect.mode is CollectMode.BOUNDED
        assert p.pandas_conversion.mode is PandasConversionMode.BOUNDED
        assert p.pandas_conversion.max_columns == 32

    def test_memory_budget_must_be_valid(self) -> None:
        # Nested validation propagates: invalid budget must reject the policy.
        with pytest.raises(ValidationError):
            ExecutionLimitPolicy(memory_budget=MemoryBudgetPolicy(max_bytes=-1))

    def test_collect_nested_validation_propagates(self) -> None:
        # Bounded collect without max_rows must reject the top-level policy.
        with pytest.raises(ValidationError):
            ExecutionLimitPolicy(
                collect=CollectPolicy(mode=CollectMode.BOUNDED),
                memory_budget=self._budget(),
            )

    def test_pandas_nested_validation_propagates(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionLimitPolicy(
                pandas_conversion=PandasConversionPolicy(mode=PandasConversionMode.BOUNDED),
                memory_budget=self._budget(),
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionLimitPolicy(  # type: ignore[call-arg]
                memory_budget=self._budget(),
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        p = ExecutionLimitPolicy(memory_budget=self._budget())
        with pytest.raises(ValidationError):
            p.metadata = {"k": "v"}  # type: ignore[misc]

    def test_round_trip(self) -> None:
        p = ExecutionLimitPolicy(
            collect=CollectPolicy(mode=CollectMode.BOUNDED, max_rows=1_000, max_bytes=4_096),
            pandas_conversion=PandasConversionPolicy(
                mode=PandasConversionMode.BOUNDED, max_rows=1_000, max_columns=32
            ),
            memory_budget=MemoryBudgetPolicy(max_bytes=1_024, scope="run"),
            metadata={"origin": "task-14"},
        )
        data = p.model_dump(mode="json")
        assert data["collect"]["mode"] == "bounded"
        assert data["collect"]["max_rows"] == 1_000
        assert data["pandas_conversion"]["mode"] == "bounded"
        assert data["memory_budget"]["max_bytes"] == 1_024
        restored = ExecutionLimitPolicy.model_validate(data)
        assert restored == p
        assert restored.collect.mode is CollectMode.BOUNDED
        assert restored.pandas_conversion.mode is PandasConversionMode.BOUNDED


# ---------------------------------------------------------------------------
# Surface guards: no raw dataframe-like object fields
# ---------------------------------------------------------------------------
def test_collect_policy_field_surface() -> None:
    allowed = {"mode", "max_rows", "max_bytes", "metadata"}
    assert set(CollectPolicy.model_fields) == allowed


def test_pandas_conversion_policy_field_surface() -> None:
    allowed = {"mode", "max_rows", "max_bytes", "max_columns", "metadata"}
    assert set(PandasConversionPolicy.model_fields) == allowed


def test_memory_budget_policy_field_surface() -> None:
    allowed = {"max_bytes", "scope", "metadata"}
    assert set(MemoryBudgetPolicy.model_fields) == allowed


def test_execution_limit_policy_field_surface() -> None:
    allowed = {"collect", "pandas_conversion", "memory_budget", "metadata"}
    assert set(ExecutionLimitPolicy.model_fields) == allowed


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_execution_limit_contracts_do_not_import_heavy_libs() -> None:
    """The execution limit contracts module must not pull heavy compute libraries."""
    import sys

    import analytics_platform.contracts.execution as exec_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by execution contracts: {leaked}"