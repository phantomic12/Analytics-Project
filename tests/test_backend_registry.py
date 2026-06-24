"""Tests for backend registry and selection (Task 83).

These tests do NOT import a real Polars backend directly — they
use a tiny stub backend to verify the registry / selection
behavior independently of the Polars runtime.
"""

from __future__ import annotations

from typing import Any

import pytest

from analytics_platform.contracts.execution import (
    BackendId,
    ExecutionBackend,
)
from analytics_platform.backends.registry import (
    BackendRegistry,
    BackendSelectionError,
    default_backend,
    default_backend_id,
    register_backend,
    select_backend,
    unregister_backend,
)


class _StubBackend:
    """Minimal backend stub used by the registry tests."""

    def __init__(self, backend_id: str) -> None:
        self.backend_id = BackendId(backend_id)
        self.backend_enum = ExecutionBackend.POLARS

    @property
    def backend_marker(self) -> str:
        return f"stub-{self.backend_id}"


@pytest.fixture
def fresh_registry() -> BackendRegistry:
    """A fresh registry, not the module-level singleton."""
    return BackendRegistry()


class TestRegistryBasics:
    def test_register_and_get(self, fresh_registry: BackendRegistry) -> None:
        backend = _StubBackend("b1")
        fresh_registry.register(backend)
        assert fresh_registry.get(BackendId("b1")) is backend

    def test_get_unknown_returns_none(
        self, fresh_registry: BackendRegistry
    ) -> None:
        assert fresh_registry.get(BackendId("missing")) is None

    def test_unregister_removes(
        self, fresh_registry: BackendRegistry
    ) -> None:
        backend = _StubBackend("b1")
        fresh_registry.register(backend)
        fresh_registry.unregister(BackendId("b1"))
        assert fresh_registry.get(BackendId("b1")) is None

    def test_unregister_unknown_is_noop(
        self, fresh_registry: BackendRegistry
    ) -> None:
        # No exception; the operation is idempotent.
        fresh_registry.unregister(BackendId("missing"))

    def test_register_overwrites(
        self, fresh_registry: BackendRegistry
    ) -> None:
        b1 = _StubBackend("b1")
        b1b = _StubBackend("b1")
        fresh_registry.register(b1)
        fresh_registry.register(b1b)
        assert fresh_registry.get(BackendId("b1")) is b1b

    def test_known_returns_sorted(
        self, fresh_registry: BackendRegistry
    ) -> None:
        fresh_registry.register(_StubBackend("c"))
        fresh_registry.register(_StubBackend("a"))
        fresh_registry.register(_StubBackend("b"))
        assert fresh_registry.known() == [
            BackendId("a"),
            BackendId("b"),
            BackendId("c"),
        ]

    def test_clear_empties(
        self, fresh_registry: BackendRegistry
    ) -> None:
        fresh_registry.register(_StubBackend("a"))
        fresh_registry.clear()
        assert fresh_registry.known() == []


class TestSelectBackend:
    def test_default_id(self) -> None:
        assert default_backend_id() == BackendId("polars-mvp")

    def test_select_unknown_raises(self) -> None:
        # Use a fresh registry via the module singleton's clear.
        from analytics_platform.backends.registry import _REGISTRY

        _REGISTRY.clear()
        with pytest.raises(BackendSelectionError) as ei:
            select_backend(BackendId("missing"))
        assert ei.value.issue.code == "BACKEND_NOT_REGISTERED"

    def test_select_with_id(self) -> None:
        from analytics_platform.backends.registry import _REGISTRY

        _REGISTRY.clear()
        backend = _StubBackend("b2")
        register_backend(backend)
        try:
            assert select_backend(BackendId("b2")) is backend
        finally:
            unregister_backend(BackendId("b2"))

    def test_select_default_uses_default_id(self) -> None:
        from analytics_platform.backends.registry import _REGISTRY

        _REGISTRY.clear()
        # Register a backend under the default id.
        backend = _StubBackend("polars-mvp")
        register_backend(backend)
        try:
            assert select_backend() is backend
            assert select_backend(None) is backend
        finally:
            unregister_backend(BackendId("polars-mvp"))

    def test_default_backend_lazy_registers(self) -> None:
        from analytics_platform.backends.registry import _REGISTRY

        _REGISTRY.clear()
        try:
            backend = default_backend()
            assert backend is not None
            # The default backend is the canonical Polars backend.
            assert backend.backend_id == default_backend_id()
            assert backend.backend_enum is ExecutionBackend.POLARS
        finally:
            unregister_backend(default_backend_id())
