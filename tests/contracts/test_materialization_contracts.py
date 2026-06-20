"""Tests for backend-neutral materialization contracts (Build Queue v2.1 Task 13).

Covers:

- ``MaterializationPolicy`` valid/invalid values and serialization.
- ``MaterializationRequest`` references an existing backend object/ref
  (``LazyFrameRef`` xor ``BackendObjectRef``), rejecting zero/multiple
  source refs and unknown/raw-object fields.
- ``MaterializationResult`` references backend/artifact targets without raw
  data, requiring at least one target reference.
- Serialization round-trip for request/result (JSON mode).
- No raw dataframe-like object fields: structural surface guards.
- Import-weight guard: no heavy compute libraries pulled by the contracts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.common import (
    ArtifactRef,
    ExecutionStatus,
)
from analytics_platform.contracts.execution import (
    BackendObjectRef,
    ExecutionBackend,
    LazyFrameRef,
    MaterializationPolicy,
    MaterializationRequest,
    MaterializationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lazy_ref() -> LazyFrameRef:
    return LazyFrameRef(
        backend=ExecutionBackend.POLARS,
        backend_id="sess-1",
        handle="lf-1",
        schema_fingerprint="sha256:abc",
        row_count_estimate=1_000,
    )


def _backend_obj_ref() -> BackendObjectRef:
    return BackendObjectRef(
        backend=ExecutionBackend.DUCKDB,
        backend_id="duck-1",
        object_kind="relation",
        handle="rel-1",
    )


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="art-1",
        kind="dataset",
        uri="file://tmp/art-1.parquet",
        run_id="run-1",
        stage_id="stage-mat",
    )


# ---------------------------------------------------------------------------
# MaterializationPolicy
# ---------------------------------------------------------------------------
class TestMaterializationPolicy:
    def test_known_members(self) -> None:
        assert MaterializationPolicy.EAGER.value == "eager"
        assert MaterializationPolicy.IN_MEMORY.value == "in_memory"
        assert MaterializationPolicy.PERSISTED.value == "persisted"
        assert MaterializationPolicy.LAZY.value == "lazy"

    def test_enum_from_value(self) -> None:
        assert MaterializationPolicy("persisted") is MaterializationPolicy.PERSISTED

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            MaterializationPolicy("streaming")  # type: ignore[arg-type]

    def test_serializes_as_plain_string(self) -> None:
        assert MaterializationPolicy.LAZY == "lazy"


# ---------------------------------------------------------------------------
# MaterializationRequest
# ---------------------------------------------------------------------------
class TestMaterializationRequest:
    def test_valid_with_lazy_frame_ref(self) -> None:
        req = MaterializationRequest(
            policy=MaterializationPolicy.EAGER,
            lazy_frame_ref=_lazy_ref(),
        )
        assert req.policy is MaterializationPolicy.EAGER
        assert req.lazy_frame_ref is not None
        assert req.backend_object_ref is None
        assert req.target_artifact is None
        assert req.target_uri is None

    def test_valid_with_backend_object_ref(self) -> None:
        req = MaterializationRequest(
            policy=MaterializationPolicy.IN_MEMORY,
            backend_object_ref=_backend_obj_ref(),
        )
        assert req.policy is MaterializationPolicy.IN_MEMORY
        assert req.backend_object_ref is not None
        assert req.lazy_frame_ref is None

    def test_valid_persisted_with_target_artifact(self) -> None:
        req = MaterializationRequest(
            policy=MaterializationPolicy.PERSISTED,
            lazy_frame_ref=_lazy_ref(),
            target_artifact=_artifact_ref(),
            target_uri="file://tmp/out.parquet",
        )
        assert req.target_artifact is not None
        assert req.target_uri == "file://tmp/out.parquet"

    def test_policy_string_coerced(self) -> None:
        req = MaterializationRequest(
            policy="lazy",  # type: ignore[arg-type]
            backend_object_ref=_backend_obj_ref(),
        )
        assert req.policy is MaterializationPolicy.LAZY

    def test_invalid_policy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationRequest(
                policy="streaming",  # type: ignore[arg-type]
                backend_object_ref=_backend_obj_ref(),
            )

    def test_no_source_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationRequest(policy=MaterializationPolicy.EAGER)

    def test_both_source_refs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationRequest(
                policy=MaterializationPolicy.EAGER,
                lazy_frame_ref=_lazy_ref(),
                backend_object_ref=_backend_obj_ref(),
            )

    def test_unknown_field_rejected(self) -> None:
        # An extra field would be the natural smuggling vector for a raw
        # dataframe object. The contract must forbid it.
        with pytest.raises(ValidationError):
            MaterializationRequest(  # type: ignore[call-arg]
                policy=MaterializationPolicy.EAGER,
                lazy_frame_ref=_lazy_ref(),
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_empty_target_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationRequest(
                policy=MaterializationPolicy.PERSISTED,
                lazy_frame_ref=_lazy_ref(),
                target_uri="",
            )

    def test_frozen(self) -> None:
        req = MaterializationRequest(
            policy=MaterializationPolicy.LAZY,
            backend_object_ref=_backend_obj_ref(),
        )
        with pytest.raises(ValidationError):
            req.policy = MaterializationPolicy.EAGER  # type: ignore[misc]

    def test_round_trip(self) -> None:
        req = MaterializationRequest(
            policy=MaterializationPolicy.PERSISTED,
            lazy_frame_ref=_lazy_ref(),
            target_artifact=_artifact_ref(),
            target_uri="file://tmp/out.parquet",
            run_id="run-1",
            stage_id="stage-mat",
            metadata={"reason": "checkpoint"},
        )
        data = req.model_dump(mode="json")
        assert data["policy"] == "persisted"
        assert data["lazy_frame_ref"]["handle"] == "lf-1"
        assert data["target_artifact"]["uri"] == "file://tmp/art-1.parquet"
        restored = MaterializationRequest.model_validate(data)
        assert restored == req
        assert restored.policy is MaterializationPolicy.PERSISTED
        assert restored.lazy_frame_ref is not None
        assert restored.lazy_frame_ref.backend is ExecutionBackend.POLARS


# ---------------------------------------------------------------------------
# MaterializationResult
# ---------------------------------------------------------------------------
class TestMaterializationResult:
    def test_valid_persisted_with_artifact(self) -> None:
        res = MaterializationResult(
            policy=MaterializationPolicy.PERSISTED,
            status=ExecutionStatus.SUCCEEDED,
            artifact=_artifact_ref(),
            rows=1_000,
            size_bytes=4096,
        )
        assert res.policy is MaterializationPolicy.PERSISTED
        assert res.status is ExecutionStatus.SUCCEEDED
        assert res.artifact is not None
        assert res.result_ref is None

    def test_valid_in_memory_with_result_ref(self) -> None:
        res = MaterializationResult(
            policy=MaterializationPolicy.IN_MEMORY,
            status=ExecutionStatus.SUCCEEDED,
            result_ref=_backend_obj_ref(),
        )
        assert res.result_ref is not None

    def test_valid_lazy_with_target_uri(self) -> None:
        res = MaterializationResult(
            policy=MaterializationPolicy.LAZY,
            status=ExecutionStatus.SUCCEEDED,
            target_uri="file://tmp/lazy.bin",
        )
        assert res.target_uri == "file://tmp/lazy.bin"

    def test_no_target_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationResult(
                policy=MaterializationPolicy.EAGER,
                status=ExecutionStatus.SUCCEEDED,
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationResult(  # type: ignore[call-arg]
                policy=MaterializationPolicy.EAGER,
                status=ExecutionStatus.SUCCEEDED,
                result_ref=_backend_obj_ref(),
                frame=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_negative_rows_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MaterializationResult(
                policy=MaterializationPolicy.PERSISTED,
                status=ExecutionStatus.SUCCEEDED,
                artifact=_artifact_ref(),
                rows=-1,
            )

    def test_round_trip(self) -> None:
        res = MaterializationResult(
            policy=MaterializationPolicy.PERSISTED,
            status=ExecutionStatus.SUCCEEDED,
            artifact=_artifact_ref(),
            target_uri="file://tmp/out.parquet",
            rows=1_000,
            size_bytes=4096,
            run_id="run-1",
            stage_id="stage-mat",
            metadata={"format": "parquet"},
        )
        data = res.model_dump(mode="json")
        assert data["policy"] == "persisted"
        assert data["status"] == "succeeded"
        assert data["artifact"]["artifact_id"] == "art-1"
        restored = MaterializationResult.model_validate(data)
        assert restored == res
        assert restored.policy is MaterializationPolicy.PERSISTED
        assert restored.status is ExecutionStatus.SUCCEEDED


# ---------------------------------------------------------------------------
# No-raw-object surface guards
# ---------------------------------------------------------------------------
def test_materialization_request_field_surface() -> None:
    allowed = {
        "policy",
        "lazy_frame_ref",
        "backend_object_ref",
        "target_artifact",
        "target_uri",
        "run_id",
        "stage_id",
        "metadata",
    }
    assert set(MaterializationRequest.model_fields) == allowed


def test_materialization_result_field_surface() -> None:
    allowed = {
        "policy",
        "status",
        "artifact",
        "target_uri",
        "result_ref",
        "rows",
        "size_bytes",
        "run_id",
        "stage_id",
        "metadata",
    }
    assert set(MaterializationResult.model_fields) == allowed


def test_materialization_request_result_refs_are_typed() -> None:
    """Source/target fields must be typed contract refs, never raw objects.

    Uses ``typing.get_args`` to compare the inner type of each ``X | None``
    Optional union by identity, since ``X | None`` union objects are not
    interned and cannot be compared with ``is``.
    """
    from typing import get_args

    req_fields = MaterializationRequest.model_fields
    assert get_args(req_fields["lazy_frame_ref"].annotation)[0] is LazyFrameRef
    assert get_args(req_fields["backend_object_ref"].annotation)[0] is BackendObjectRef
    assert get_args(req_fields["target_artifact"].annotation)[0] is ArtifactRef

    res_fields = MaterializationResult.model_fields
    assert get_args(res_fields["artifact"].annotation)[0] is ArtifactRef
    assert get_args(res_fields["result_ref"].annotation)[0] is BackendObjectRef


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_materialization_contracts_do_not_import_heavy_libs() -> None:
    """The execution contracts module must not pull heavy compute libraries."""
    import sys

    import analytics_platform.contracts.execution as exec_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by execution contracts: {leaked}"