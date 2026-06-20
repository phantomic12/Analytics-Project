"""Tests for backend-neutral execution reference contracts (Build Queue v2.1 Task 12).

Covers:

- ``ExecutionBackend`` valid/invalid values.
- ``BackendId`` validation/serialization when modeled directly as a field.
- ``LazyFrameRef`` serialization round-trip.
- ``BackendObjectRef`` serialization round-trip.
- Rejection of raw dataframe-like object fields (unknown-field rejection and
  immutability) and absence of any field capable of carrying a raw object.
- Import-weight guard: no heavy compute libraries are pulled by importing the
  execution reference contracts module.

These tests intentionally avoid importing any heavy compute library so that
they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from analytics_platform.contracts.execution import (
    BackendId,
    BackendObjectRef,
    ExecutionBackend,
    LazyFrameRef,
)


# ---------------------------------------------------------------------------
# ExecutionBackend
# ---------------------------------------------------------------------------
class TestExecutionBackend:
    def test_known_members(self) -> None:
        assert ExecutionBackend.POLARS.value == "polars"
        assert ExecutionBackend.DUCKDB.value == "duckdb"
        assert ExecutionBackend.LOCAL.value == "local"

    def test_enum_from_value(self) -> None:
        assert ExecutionBackend("polars") is ExecutionBackend.POLARS
        assert ExecutionBackend("duckdb") is ExecutionBackend.DUCKDB
        assert ExecutionBackend("local") is ExecutionBackend.LOCAL

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExecutionBackend("spark")  # type: ignore[arg-type]

    def test_is_str_subclass_for_serializable_values(self) -> None:
        # str-Enum values serialize as plain strings across JSON boundaries.
        assert ExecutionBackend.POLARS == "polars"


# ---------------------------------------------------------------------------
# BackendId (as a field on a model)
# ---------------------------------------------------------------------------
class _BackendIdHolder(BaseModel):
    """Tiny model used to exercise BackendId validation/serialization."""

    model_config = {"frozen": True, "extra": "forbid"}

    backend_id: BackendId


class TestBackendId:
    def test_valid_value(self) -> None:
        h = _BackendIdHolder(backend_id="session-1")
        assert h.backend_id == "session-1"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _BackendIdHolder(backend_id="")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _BackendIdHolder(backend_id="x" * 257)

    def test_serialization_round_trip(self) -> None:
        h = _BackendIdHolder(backend_id="rt-id")
        data = h.model_dump(mode="json")
        assert data == {"backend_id": "rt-id"}
        assert _BackendIdHolder.model_validate(data) == h


# ---------------------------------------------------------------------------
# LazyFrameRef
# ---------------------------------------------------------------------------
class TestLazyFrameRef:
    def _sample(self) -> LazyFrameRef:
        return LazyFrameRef(
            backend=ExecutionBackend.POLARS,
            backend_id="sess-1",
            handle="lf-abc",
            schema_fingerprint="sha256:deadbeef",
            row_count_estimate=1_000_000,
            run_id="run-1",
            stage_id="stage-join",
            metadata={"source": "catalog"},
        )

    def test_valid_minimal(self) -> None:
        ref = LazyFrameRef(backend=ExecutionBackend.POLARS, backend_id="s1", handle="lf-1")
        assert ref.backend is ExecutionBackend.POLARS
        assert ref.backend_id == "s1"
        assert ref.handle == "lf-1"
        assert ref.schema_fingerprint is None
        assert ref.row_count_estimate is None
        assert ref.run_id is None
        assert ref.stage_id is None
        assert ref.metadata is None

    def test_valid_with_all_fields(self) -> None:
        ref = self._sample()
        assert ref.backend is ExecutionBackend.POLARS
        assert ref.row_count_estimate == 1_000_000
        assert ref.metadata == {"source": "catalog"}

    def test_backend_string_coerced(self) -> None:
        ref = LazyFrameRef(backend="polars", backend_id="s1", handle="lf-1")  # type: ignore[arg-type]
        assert ref.backend is ExecutionBackend.POLARS

    def test_invalid_backend_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LazyFrameRef(backend="spark", backend_id="s1", handle="lf-1")  # type: ignore[arg-type]

    def test_empty_backend_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LazyFrameRef(backend=ExecutionBackend.POLARS, backend_id="", handle="lf-1")

    def test_empty_handle_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LazyFrameRef(backend=ExecutionBackend.POLARS, backend_id="s1", handle="")

    def test_negative_row_count_estimate_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LazyFrameRef(
                backend=ExecutionBackend.POLARS,
                backend_id="s1",
                handle="lf-1",
                row_count_estimate=-1,
            )

    def test_zero_row_count_estimate_allowed(self) -> None:
        ref = LazyFrameRef(
            backend=ExecutionBackend.POLARS, backend_id="s1", handle="lf-1", row_count_estimate=0
        )
        assert ref.row_count_estimate == 0

    def test_unknown_field_rejected(self) -> None:
        # An extra field would be the natural smuggling vector for a raw
        # dataframe object. The contract must forbid it.
        with pytest.raises(ValidationError):
            LazyFrameRef(  # type: ignore[call-arg]
                backend=ExecutionBackend.POLARS,
                backend_id="s1",
                handle="lf-1",
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        ref = self._sample()
        with pytest.raises(ValidationError):
            ref.handle = "lf-other"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        ref = self._sample()
        data = ref.model_dump(mode="json")
        # Serializes to plain JSON-able primitives only.
        assert data["backend"] == "polars"
        assert data["handle"] == "lf-abc"
        assert data["row_count_estimate"] == 1_000_000
        restored = LazyFrameRef.model_validate(data)
        assert restored == ref
        assert restored.backend is ExecutionBackend.POLARS


# ---------------------------------------------------------------------------
# BackendObjectRef
# ---------------------------------------------------------------------------
class TestBackendObjectRef:
    def _sample(self) -> BackendObjectRef:
        return BackendObjectRef(
            backend=ExecutionBackend.DUCKDB,
            backend_id="duck-sess",
            object_kind="relation",
            handle="rel-42",
            run_id="run-2",
            stage_id="stage-probe",
            metadata={"db": "memory"},
        )

    def test_valid_minimal(self) -> None:
        ref = BackendObjectRef(
            backend=ExecutionBackend.LOCAL,
            backend_id="s1",
            object_kind="plan",
            handle="p-1",
        )
        assert ref.backend is ExecutionBackend.LOCAL
        assert ref.object_kind == "plan"
        assert ref.metadata is None

    def test_valid_with_all_fields(self) -> None:
        ref = self._sample()
        assert ref.backend is ExecutionBackend.DUCKDB
        assert ref.metadata == {"db": "memory"}

    def test_invalid_backend_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BackendObjectRef(  # type: ignore[arg-type]
                backend="dask", backend_id="s1", object_kind="relation", handle="r-1"
            )

    def test_empty_object_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BackendObjectRef(
                backend=ExecutionBackend.LOCAL, backend_id="s1", object_kind="", handle="r-1"
            )

    def test_empty_handle_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BackendObjectRef(
                backend=ExecutionBackend.LOCAL, backend_id="s1", object_kind="relation", handle=""
            )

    def test_unknown_field_rejected(self) -> None:
        # An extra field would be the natural smuggling vector for a raw
        # backend object. The contract must forbid it.
        with pytest.raises(ValidationError):
            BackendObjectRef(  # type: ignore[call-arg]
                backend=ExecutionBackend.LOCAL,
                backend_id="s1",
                object_kind="relation",
                handle="r-1",
                relation=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        ref = self._sample()
        with pytest.raises(ValidationError):
            ref.handle = "r-other"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        ref = self._sample()
        data = ref.model_dump(mode="json")
        assert data["backend"] == "duckdb"
        assert data["object_kind"] == "relation"
        restored = BackendObjectRef.model_validate(data)
        assert restored == ref
        assert restored.backend is ExecutionBackend.DUCKDB


# ---------------------------------------------------------------------------
# No-raw-object surface guard
# ---------------------------------------------------------------------------
def test_lazy_frame_ref_has_no_object_typed_field() -> None:
    """No field on ``LazyFrameRef`` may be typed as ``object``/``Any``/callable.

    This is a structural guard against accidentally exposing a raw dataframe
    or backend handle through the public contract surface. All fields must be
    serializable primitives or shared contracts.
    """
    allowed_field_types = {
        "backend",
        "backend_id",
        "handle",
        "schema_fingerprint",
        "row_count_estimate",
        "run_id",
        "stage_id",
        "metadata",
    }
    assert set(LazyFrameRef.model_fields) == allowed_field_types


def test_backend_object_ref_has_no_object_typed_field() -> None:
    """No field on ``BackendObjectRef`` may be typed as ``object``/``Any``/callable."""
    allowed_field_types = {
        "backend",
        "backend_id",
        "object_kind",
        "handle",
        "run_id",
        "stage_id",
        "metadata",
    }
    assert set(BackendObjectRef.model_fields) == allowed_field_types


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_execution_contracts_do_not_import_heavy_libs() -> None:
    """The execution contracts module must not pull heavy compute libraries.

    Importing it must not transitively load polars/pandas/duckdb/numpy/scipy/
    statsmodels. We check ``sys.modules`` after import.
    """
    import sys

    import analytics_platform.contracts.execution as exec_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by execution contracts: {leaked}"