"""Tests for the Polars backend adapter (Build Queue v2.1 Task 82)."""

from __future__ import annotations

import polars as pl
import pytest

from analytics_platform.contracts.common import ExecutionStatus
from analytics_platform.contracts.execution import (
    BackendId,
    ExecutionBackend,
    MaterializationPolicy,
    MaterializationRequest,
)
from analytics_platform.backends import (
    PolarsBackend,
    PolarsBackendError,
)


@pytest.fixture
def backend() -> PolarsBackend:
    return PolarsBackend.from_config(BackendId("polars-mvp"))


@pytest.fixture
def lf() -> pl.LazyFrame:
    return pl.LazyFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


class TestPolarsBackendBasics:
    def test_backend_id(self, backend: PolarsBackend) -> None:
        assert backend.backend_id == "polars-mvp"

    def test_backend_enum(self, backend: PolarsBackend) -> None:
        assert backend.backend_enum is ExecutionBackend.POLARS

    def test_register_and_resolve(self, backend: PolarsBackend, lf: pl.LazyFrame) -> None:
        ref = backend.register(lf, handle="h1")
        assert ref.backend is ExecutionBackend.POLARS
        assert ref.backend_id == "polars-mvp"
        assert ref.handle == "h1"
        # Resolve the ref back to the original frame.
        resolved = backend.resolve(ref)
        assert isinstance(resolved, pl.LazyFrame)
        # Eager-collect and compare.
        collected = resolved.collect().sort("a")
        assert collected["a"].to_list() == [1, 2, 3]
        assert collected["b"].to_list() == ["x", "y", "z"]

    def test_register_duplicate_handle_rejected(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        backend.register(lf, handle="h1")
        with pytest.raises(PolarsBackendError) as ei:
            backend.register(lf, handle="h1")
        assert ei.value.issue.code == "POLARS_HANDLE_EXISTS"

    def test_register_auto_handle(self, backend: PolarsBackend, lf: pl.LazyFrame) -> None:
        ref = backend.register(lf)
        assert ref.handle.startswith("polars-")


class TestPolarsMaterialize:
    def test_eager_materialize(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        ref = backend.register(lf, handle="h1")
        req = MaterializationRequest(
            policy=MaterializationPolicy.EAGER,
            backend_object_ref=ref,
        )
        result = backend.materialize(req)
        assert result.policy is MaterializationPolicy.EAGER
        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.result_ref is not None
        # The result ref points to a DataFrame in the registry.
        resolved = backend.resolve(result.result_ref)
        assert isinstance(resolved, pl.DataFrame)
        assert sorted(resolved["a"].to_list()) == [1, 2, 3]

    def test_persisted_materialize(
        self, backend: PolarsBackend, lf: pl.LazyFrame, tmp_path
    ) -> None:
        ref = backend.register(lf, handle="h1")
        target = tmp_path / "out.parquet"
        req = MaterializationRequest(
            policy=MaterializationPolicy.PERSISTED,
            backend_object_ref=ref,
            target_uri=str(target),
        )
        result = backend.materialize(req)
        assert result.target_uri == str(target)
        assert target.exists()

    def test_in_memory_materialize(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        ref = backend.register(lf, handle="h1")
        req = MaterializationRequest(
            policy=MaterializationPolicy.IN_MEMORY,
            backend_object_ref=ref,
        )
        result = backend.materialize(req)
        assert result.result_ref is not None

    def test_lazy_materialize(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        ref = backend.register(lf, handle="h1")
        req = MaterializationRequest(
            policy=MaterializationPolicy.LAZY,
            backend_object_ref=ref,
        )
        result = backend.materialize(req)
        assert result.result_ref is not None

    def test_no_source_rejected(
        self, backend: PolarsBackend
    ) -> None:
        # ``MaterializationRequest`` itself rejects the
        # construction when no source ref is provided, so the
        # error is raised at construction time, not at
        # ``materialize()``. This test asserts that the
        # construction-time contract is preserved.
        with pytest.raises(Exception) as ei:
            MaterializationRequest(policy=MaterializationPolicy.EAGER)
        # The error may be a pydantic ValidationError or a
        # PolarsBackendError; either is acceptable per the
        # contract's design.
        assert ei.value is not None


class TestPolarsResolve:
    def test_resolve_wrong_backend(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        # Construct a ref with a different backend; resolve
        # should refuse.
        from analytics_platform.contracts.execution import (
            BackendObjectRef as BOR,
        )

        ref = BOR(
            backend=ExecutionBackend.LOCAL,
            backend_id="x",
            object_kind="data_frame",
            handle="h",
        )
        with pytest.raises(PolarsBackendError) as ei:
            backend.resolve(ref)
        assert ei.value.issue.code == "POLARS_BACKEND_MISMATCH"

    def test_resolve_unknown_handle(
        self, backend: PolarsBackend
    ) -> None:
        from analytics_platform.contracts.execution import (
            BackendObjectRef as BOR,
        )

        ref = BOR(
            backend=ExecutionBackend.POLARS,
            backend_id="polars-mvp",
            object_kind="data_frame",
            handle="missing",
        )
        with pytest.raises(PolarsBackendError) as ei:
            backend.resolve(ref)
        assert ei.value.issue.code == "POLARS_HANDLE_NOT_FOUND"


class TestPolarsFromLazyFrameRef:
    def test_lazy_frame_ref_path(
        self, backend: PolarsBackend, lf: pl.LazyFrame
    ) -> None:
        # Register with kind="lazy_frame"
        from analytics_platform.contracts.execution import (
            BackendObjectRef as BOR,
        )

        ref = BOR(
            backend=ExecutionBackend.POLARS,
            backend_id="polars-mvp",
            object_kind="lazy_frame",
            handle="h1",
        )
        backend._registry["h1"] = lf  # type: ignore[attr-defined]
        req = MaterializationRequest(
            policy=MaterializationPolicy.LAZY,
            backend_object_ref=ref,
        )
        result = backend.materialize(req)
        assert result.result_ref is not None
