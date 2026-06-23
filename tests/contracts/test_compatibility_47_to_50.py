"""Compatibility tests (Build Queue v2.1 Tasks 47-50).

Per the interface map (sections 4.1-4.7) and the contract-test
plan (section 4.6: Downstream compatibility tests), every public
contract must be consumable by every documented allowed consumer
without forcing the consumer to import heavy libraries. These
tests assert the cross-family compatibility described in
``docs/contracts/contracts-index-v1.1.md`` table 3.

Tasks 47-50:

- Task 47: Config -> Pipeline compatibility.
- Task 48: Execution -> Dataset compatibility.
- Task 49: Execution-limits -> Backend compatibility.
- Task 50: Artifact -> Cache compatibility.

These tests are *configuration-shape* tests: they construct a
config object that the upstream family produces, hand it to the
downstream family's input shape, and assert that the downstream
type accepts it. They are not runtime tests; the implementation
of each cross-stage pass is deferred to later implementation
tasks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactHashAlgorithm,
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
    PersistedArtifact,
)
from analytics_platform.contracts.cache import (
    CacheFingerprint,
    CacheKey,
    CacheStatus,
    InvalidationReason,
)
from config_pipeline_compat import (
    ConfigToPipelineAdapter,
)
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetLoadRequest,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    MaterializationPolicy,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)
from execution_dataset_compat import (
    ExecutionToDatasetAdapter,
)
from execution_limits_backend_compat import (
    ExecutionLimitsToBackendAdapter,
)
from analytics_platform.contracts.pipeline import (
    AnalysisPlan,
    PipelineExecutionMode,
    PipelineFailurePolicy,
    PipelineStageName,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _limits() -> ExecutionLimitPolicy:
    return ExecutionLimitPolicy(
        collect=CollectPolicy(mode=CollectMode.BOUNDED, max_rows=10_000),
        pandas_conversion=PandasConversionPolicy(
            mode=PandasConversionMode.BOUNDED, max_rows=10_000
        ),
        memory_budget=MemoryBudgetPolicy(max_bytes=2_000_000_000),
    )


def _hash() -> ArtifactHash:
    return ArtifactHash(algorithm=ArtifactHashAlgorithm.SHA256, digest="abc")


def _storage() -> ArtifactStoragePolicy:
    return ArtifactStoragePolicy(
        medium=ArtifactStorageMedium.LOCAL_FS,
        retention=ArtifactRetention.PERSISTENT,
    )


def _persisted_artifact(artifact_id: str = "a1") -> PersistedArtifact:
    return PersistedArtifact(
        artifact_id=artifact_id,
        kind="dataset",
        location="/data/x.parquet",
        hash=_hash(),
        storage_policy=_storage(),
    )


# ---------------------------------------------------------------------------
# Task 47: Config -> Pipeline compatibility
# ---------------------------------------------------------------------------
class TestConfigToPipelineCompatibility:
    """The configuration that loads a plan must produce a valid
    :class:`AnalysisPlan`.

    Per the interface map (stage 4.1), the config-loading stage
    returns an ``AnalysisPlan`` that drives every subsequent stage.
    The compatibility test ensures the canonical plan shape
    produced by config-loading is accepted by the pipeline entry
    point.
    """

    def test_canonical_config_produces_valid_plan(self) -> None:
        plan = ConfigToPipelineAdapter.build_plan(
            plan_id="p1",
            dataset=_handle(),
            stages=(PipelineStageName.DATASET_LOAD,),
        )
        assert isinstance(plan, AnalysisPlan)
        assert plan.plan_id == "p1"
        assert PipelineStageName.DATASET_LOAD in plan.stages

    def test_pipeline_plan_accepts_minimal_config(self) -> None:
        plan = AnalysisPlan(
            plan_id="p1",
            datasets=(_handle(),),
            stages=(PipelineStageName.DATASET_LOAD,),
        )
        assert plan.execution_mode is PipelineExecutionMode.NORMAL
        assert plan.failure_policy is PipelineFailurePolicy.FAIL_FAST

    def test_empty_stages_from_config_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(_handle(),),
                stages=(),
            )

    def test_empty_datasets_from_config_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisPlan(
                plan_id="p1",
                datasets=(),
                stages=(PipelineStageName.DATASET_LOAD,),
            )


# ---------------------------------------------------------------------------
# Task 48: Execution -> Dataset compatibility
# ---------------------------------------------------------------------------
class TestExecutionToDatasetCompatibility:
    """The :class:`BackendObjectRef` / :class:`LazyFrameRef` produced
    by an execution backend must be a valid input to the
    :class:`DatasetLoadRequest`.

    Per the contract-test plan section 4.6, downstream modules
    construct request / result objects from documented fields
    only. The :class:`ExecutionToDatasetAdapter` is the canonical
    way an execution backend's output flows into the dataset
    registration stage.
    """

    def test_persisted_artifact_uri_is_accepted_by_load_request(self) -> None:
        artifact = _persisted_artifact()
        uri = ExecutionToDatasetAdapter.extract_dataset_uri(artifact)
        load_request = DatasetLoadRequest(
            source_uri=uri,
            format=DatasetFormat.PARQUET,
        )
        assert load_request.source_uri == "/data/x.parquet"
        assert load_request.format is DatasetFormat.PARQUET

    def test_dataset_handle_compatibility(self) -> None:
        # A DatasetLoadRequest's source_uri / format / storage_backend
        # are accepted by a DatasetHandle that mirrors the request.
        load_request = DatasetLoadRequest(
            source_uri="/data/orders.csv",
            format=DatasetFormat.CSV,
            storage_backend=StorageBackend.LOCAL_FS,
        )
        handle = DatasetHandle(
            dataset_id="d1",
            dataset_ref=DatasetRef("ds-v1"),
            name="orders",
            format=load_request.format,
            storage_backend=load_request.storage_backend,
            materialization_status=DatasetMaterializationStatus.MATERIALIZED,
        )
        assert handle.format is load_request.format
        assert handle.storage_backend is load_request.storage_backend

    def test_default_materialization_policy(self) -> None:
        # The adapter's default materialization policy is the
        # canonical choice for execution -> dataset bridges.
        assert (
            ExecutionToDatasetAdapter.default_materialization_policy()
            is MaterializationPolicy.EAGER
        )


# ---------------------------------------------------------------------------
# Task 49: Execution-limits -> Backend compatibility
# ---------------------------------------------------------------------------
class TestExecutionLimitsToBackendCompatibility:
    """The :class:`ExecutionLimitPolicy` produced by the upstream
    policy stage must be accepted by every backend-family request
    shape.

    Per the architecture-test plan (section 3.4) and the
    contract-test plan (section 4.6), downstream modules consume
    request/result objects from documented fields only. An
    :class:`ExecutionLimitPolicy` is the canonical way a backend
    is told how to bound its work; the policy must be accepted by
    the backend-family request shapes (``MaterializationRequest``,
    ``DatasetLoadRequest``, etc.).
    """

    def test_policy_constructed_from_backend_knobs(self) -> None:
        p = ExecutionLimitsToBackendAdapter.from_backend_knobs(
            max_rows=1000,
            max_columns=50,
            max_bytes=1_000_000,
        )
        assert p.memory_budget.max_bytes == 1_000_000
        assert p.collect.max_rows == 1000
        assert p.pandas_conversion.max_rows == 1000

    def test_policy_negative_knobs_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExecutionLimitsToBackendAdapter.from_backend_knobs(max_rows=-1, max_bytes=100)

    def test_policy_with_max_columns_none(self) -> None:
        p = ExecutionLimitsToBackendAdapter.from_backend_knobs(max_rows=1000, max_bytes=1_000_000)
        assert p.memory_budget.max_bytes == 1_000_000


# ---------------------------------------------------------------------------
# Task 50: Artifact -> Cache compatibility
# ---------------------------------------------------------------------------
class TestArtifactToCacheCompatibility:
    """The :class:`PersistedArtifact` produced by the artifact
    family must be a valid input to a :class:`CacheKey` /
    :class:`CacheFingerprint`.

    Per the contract-test plan (section 4.6), adding a new field
    to one contract must not break documented downstream consumers.
    The cache family is the canonical downstream consumer of
    artifact-family references; the cache-key shape must accept a
    persisted artifact and produce a valid cache record.
    """

    def test_artifact_hash_accepted_by_cache_fingerprint(self) -> None:
        artifact = _persisted_artifact()
        fp = CacheFingerprint(
            kind="artifact",
            hash=artifact.hash,
        )
        assert fp.hash.algorithm == artifact.hash.algorithm
        assert fp.hash.digest == artifact.hash.digest

    def test_artifact_id_accepted_by_cache_key(self) -> None:
        artifact = _persisted_artifact("a-42")
        fp = CacheFingerprint(kind="artifact", hash=artifact.hash)
        key = CacheKey(namespace="cache-test", fingerprints=(fp,))
        assert key.artifact_id is None  # not set, but accepted

    def test_cache_key_with_artifact_id(self) -> None:
        artifact = _persisted_artifact("a-99")
        fp = CacheFingerprint(kind="artifact", hash=artifact.hash)
        key = CacheKey(
            namespace="cache-test",
            fingerprints=(fp,),
            artifact_id=artifact.artifact_id,
        )
        assert key.artifact_id == "a-99"

    def test_cache_status_enum_complete(self) -> None:
        statuses = {s.value for s in CacheStatus}
        assert "hit" in statuses
        assert "miss" in statuses
        assert "stale" in statuses

    def test_invalidation_reasons_enum_complete(self) -> None:
        # InvalidationReason is a model with a code enum; verify
        # the canonical codes are present.
        from analytics_platform.contracts.cache import InvalidationReasonCode

        codes = {c.value for c in InvalidationReasonCode}
        assert "changed_input" in codes
        assert "changed_config" in codes
        assert "policy_invalidation" in codes

    def test_cache_round_trip(self) -> None:
        fp = CacheFingerprint(
            kind="artifact",
            hash=ArtifactHash(
                algorithm=ArtifactHashAlgorithm.SHA256,
                digest="abc",
            ),
        )
        assert CacheFingerprint.model_validate(fp.model_dump(mode="json")) == fp
