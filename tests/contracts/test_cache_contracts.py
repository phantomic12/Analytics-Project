"""Tests for cache invalidation contracts (Build Queue v2.1 Task 16).

Covers ``CacheStatus``, ``InvalidationReasonCode``, ``InvalidationReason``,
``CacheFingerprint``, and ``CacheKey``: validation, defaults, serialization
round-trips, representation of changed input/config/code/dependency/artifact and
missing/stale artifacts, rejection of invalid status/reason, surface guards
against raw dataframe-like fields, and an import-weight guard. These tests
avoid heavy compute libraries and do not implement runtime cache storage, cache
manager, artifact store, manifest, registry, or pipeline cache behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import ArtifactHash, ArtifactHashAlgorithm
from analytics_platform.contracts.cache import (
    CacheFingerprint,
    CacheKey,
    CacheStatus,
    InvalidationReason,
    InvalidationReasonCode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash(digest: str = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789") -> ArtifactHash:
    return ArtifactHash(algorithm=ArtifactHashAlgorithm.SHA256, digest=digest)


def _fingerprint(kind: str = "input", digest: str = "abc") -> CacheFingerprint:
    return CacheFingerprint(kind=kind, hash=_hash(digest=digest))


def _key(fingerprints=None) -> CacheKey:
    if fingerprints is None:
        fingerprints = (_fingerprint(kind="input"),)
    return CacheKey(namespace="stage-io", fingerprints=fingerprints)


# ---------------------------------------------------------------------------
# CacheStatus
# ---------------------------------------------------------------------------
class TestCacheStatus:
    def test_known_members(self) -> None:
        assert CacheStatus.HIT.value == "hit"
        assert CacheStatus.MISS.value == "miss"
        assert CacheStatus.STALE.value == "stale"
        assert CacheStatus.INVALIDATED.value == "invalidated"
        assert CacheStatus.BYPASSED.value == "bypassed"

    def test_enum_from_value(self) -> None:
        assert CacheStatus("stale") is CacheStatus.STALE

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            CacheStatus("not-a-status")  # type: ignore[arg-type]

    def test_serializes_as_plain_string(self) -> None:
        assert CacheStatus.HIT == "hit"


# ---------------------------------------------------------------------------
# InvalidationReasonCode / InvalidationReason
# ---------------------------------------------------------------------------
class TestInvalidationReasonCode:
    def test_known_members(self) -> None:
        assert InvalidationReasonCode.CHANGED_INPUT.value == "changed_input"
        assert InvalidationReasonCode.CHANGED_CONFIG.value == "changed_config"
        assert InvalidationReasonCode.CHANGED_CODE.value == "changed_code"
        assert InvalidationReasonCode.CHANGED_DEPENDENCY.value == "changed_dependency"
        assert InvalidationReasonCode.CHANGED_ARTIFACT.value == "changed_artifact"
        assert InvalidationReasonCode.MISSING_ARTIFACT.value == "missing_artifact"
        assert InvalidationReasonCode.POLICY_INVALIDATION.value == "policy_invalidation"
        assert InvalidationReasonCode.MANUAL_INVALIDATION.value == "manual_invalidation"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            InvalidationReasonCode("not-a-reason")  # type: ignore[arg-type]


class TestInvalidationReason:
    def test_valid(self) -> None:
        r = InvalidationReason(code=InvalidationReasonCode.CHANGED_INPUT)
        assert r.code is InvalidationReasonCode.CHANGED_INPUT
        assert r.detail is None
        assert r.changed_ref is None

    def test_with_provenance(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_CONFIG,
            detail="config hash changed",
            changed_ref="config:defaults",
            run_id="run-1",
            stage_id="stage-io",
            metadata={"key": "value"},
        )
        assert r.detail == "config hash changed"
        assert r.changed_ref == "config:defaults"
        assert r.run_id == "run-1"
        assert r.stage_id == "stage-io"
        assert r.metadata == {"key": "value"}

    def test_invalid_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InvalidationReason(code="not-a-reason")  # type: ignore[arg-type]

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InvalidationReason(  # type: ignore[call-arg]
                code=InvalidationReasonCode.CHANGED_INPUT,
                dataframe=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        r = InvalidationReason(code=InvalidationReasonCode.CHANGED_INPUT)
        with pytest.raises(ValidationError):
            r.code = InvalidationReasonCode.CHANGED_CONFIG  # type: ignore[misc]

    def test_round_trip(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_CODE,
            detail="code hash changed",
            changed_ref="src/module.py",
            run_id="run-1",
            stage_id="stage-io",
            metadata={"origin": "task-16"},
        )
        data = r.model_dump(mode="json")
        assert data["code"] == "changed_code"
        restored = InvalidationReason.model_validate(data)
        assert restored == r
        assert restored.code is InvalidationReasonCode.CHANGED_CODE


# ---------------------------------------------------------------------------
# CacheFingerprint
# ---------------------------------------------------------------------------
class TestCacheFingerprint:
    def test_valid(self) -> None:
        fp = _fingerprint(kind="input")
        assert fp.kind == "input"
        assert fp.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert fp.label is None
        assert fp.source_ref is None

    def test_with_label_and_source(self) -> None:
        fp = CacheFingerprint(
            kind="config",
            hash=_hash(),
            label="defaults.yaml",
            source_ref="config://defaults",
        )
        assert fp.label == "defaults.yaml"
        assert fp.source_ref == "config://defaults"

    def test_missing_required_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheFingerprint(hash=_hash())  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            CacheFingerprint(kind="input")  # type: ignore[call-arg]

    def test_empty_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheFingerprint(kind="", hash=_hash())

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheFingerprint(  # type: ignore[call-arg]
                kind="input",
                hash=_hash(),
                payload=b"bytes",  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        fp = _fingerprint()
        with pytest.raises(ValidationError):
            fp.kind = "config"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        fp = CacheFingerprint(
            kind="code",
            hash=_hash(digest="deadbeef"),
            label="src/lib.py",
            source_ref="git://abc",
        )
        data = fp.model_dump(mode="json")
        assert data["kind"] == "code"
        assert data["hash"]["algorithm"] == "sha256"
        restored = CacheFingerprint.model_validate(data)
        assert restored == fp
        assert restored.hash.algorithm is ArtifactHashAlgorithm.SHA256


# ---------------------------------------------------------------------------
# CacheKey
# ---------------------------------------------------------------------------
class TestCacheKey:
    def test_valid(self) -> None:
        k = _key()
        assert k.namespace == "stage-io"
        assert len(k.fingerprints) == 1
        assert k.fingerprints[0].kind == "input"
        assert k.run_id is None
        assert k.stage_id is None
        assert k.artifact_id is None

    def test_multiple_fingerprints(self) -> None:
        k = CacheKey(
            namespace="stage-model",
            fingerprints=(
                _fingerprint(kind="input", digest="aaa"),
                _fingerprint(kind="config", digest="bbb"),
                _fingerprint(kind="code", digest="ccc"),
            ),
            run_id="run-1",
            stage_id="stage-model",
            artifact_id="art-1",
            metadata={"tier": "hot"},
        )
        assert len(k.fingerprints) == 3
        assert {fp.kind for fp in k.fingerprints} == {"input", "config", "code"}
        assert k.artifact_id == "art-1"

    def test_missing_required_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheKey(fingerprints=(_fingerprint(),))  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            CacheKey(namespace="stage-io")  # type: ignore[call-arg]

    def test_empty_fingerprints_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheKey(namespace="stage-io", fingerprints=())

    def test_empty_namespace_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheKey(namespace="", fingerprints=(_fingerprint(),))

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CacheKey(  # type: ignore[call-arg]
                namespace="stage-io",
                fingerprints=(_fingerprint(),),
                dataframe=object(),  # noqa: NOT_USED -- intentionally rejected
            )

    def test_frozen(self) -> None:
        k = _key()
        with pytest.raises(ValidationError):
            k.namespace = "stage-model"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        k = CacheKey(
            namespace="stage-io",
            fingerprints=(
                _fingerprint(kind="input", digest="aaa"),
                _fingerprint(kind="config", digest="bbb"),
            ),
            run_id="run-1",
            stage_id="stage-io",
            artifact_id="art-1",
            metadata={"origin": "task-16"},
        )
        data = k.model_dump(mode="json")
        assert data["namespace"] == "stage-io"
        assert len(data["fingerprints"]) == 2
        assert data["fingerprints"][0]["hash"]["algorithm"] == "sha256"
        restored = CacheKey.model_validate(data)
        assert restored == k
        assert restored.fingerprints[0].hash.algorithm is ArtifactHashAlgorithm.SHA256


# ---------------------------------------------------------------------------
# Invalidation scenarios: changed input/config/code/dependency/artifact +
# missing/stale artifact
# ---------------------------------------------------------------------------
class TestInvalidationScenarios:
    def test_changed_input_invalidates(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_INPUT,
            detail="input dataset hash changed",
            changed_ref="dataset:ds-1",
        )
        assert r.code is InvalidationReasonCode.CHANGED_INPUT
        assert r.changed_ref == "dataset:ds-1"

    def test_changed_config_invalidates(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_CONFIG,
            detail="config hash changed",
            changed_ref="config:defaults",
        )
        assert r.code is InvalidationReasonCode.CHANGED_CONFIG

    def test_changed_code_invalidates(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_CODE,
            detail="code hash changed",
            changed_ref="src/module.py",
        )
        assert r.code is InvalidationReasonCode.CHANGED_CODE

    def test_changed_dependency_invalidates(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_DEPENDENCY,
            detail="upstream dependency changed",
            changed_ref="stage:upstream",
        )
        assert r.code is InvalidationReasonCode.CHANGED_DEPENDENCY

    def test_changed_artifact_representable(self) -> None:
        r = InvalidationReason(
            code=InvalidationReasonCode.CHANGED_ARTIFACT,
            detail="referenced artifact hash changed",
            changed_ref="artifact:art-1",
        )
        assert r.code is InvalidationReasonCode.CHANGED_ARTIFACT

    def test_missing_artifact_representable(self) -> None:
        # status path
        assert CacheStatus.STALE.value == "stale"
        assert CacheStatus.INVALIDATED.value == "invalidated"
        # reason path
        r = InvalidationReason(
            code=InvalidationReasonCode.MISSING_ARTIFACT,
            detail="referenced artifact not found",
            changed_ref="artifact:art-1",
        )
        assert r.code is InvalidationReasonCode.MISSING_ARTIFACT

    def test_policy_and_manual_invalidation_representable(self) -> None:
        assert InvalidationReasonCode.POLICY_INVALIDATION.value == "policy_invalidation"
        assert InvalidationReasonCode.MANUAL_INVALIDATION.value == "manual_invalidation"


# ---------------------------------------------------------------------------
# Surface guards: no raw dataframe-like object fields
# ---------------------------------------------------------------------------
def test_cache_status_members() -> None:
    assert {s.value for s in CacheStatus} == {
        "hit", "miss", "stale", "invalidated", "bypassed"
    }


def test_invalidation_reason_code_members() -> None:
    assert {c.value for c in InvalidationReasonCode} == {
        "changed_input", "changed_config", "changed_code", "changed_dependency",
        "changed_artifact", "missing_artifact", "policy_invalidation",
        "manual_invalidation",
    }


def test_invalidation_reason_field_surface() -> None:
    assert set(InvalidationReason.model_fields) == {
        "code", "detail", "changed_ref", "run_id", "stage_id", "metadata"
    }


def test_cache_fingerprint_field_surface() -> None:
    assert set(CacheFingerprint.model_fields) == {
        "kind", "hash", "label", "source_ref"
    }


def test_cache_key_field_surface() -> None:
    assert set(CacheKey.model_fields) == {
        "namespace", "fingerprints", "run_id", "stage_id", "artifact_id", "metadata"
    }


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_cache_contracts_do_not_import_heavy_libs() -> None:
    """The cache contracts module must not pull heavy compute libraries."""
    import sys

    import analytics_platform.contracts.cache as cache_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by cache contracts: {leaked}"