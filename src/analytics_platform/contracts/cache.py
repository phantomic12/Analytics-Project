"""Cache invalidation contracts (Build Queue v2.1 Task 16).

Public, dependency-light contracts that describe *how later runtime/cache,
manifest, registry, and pipeline-cache code may represent cache keys,
fingerprints, status, and invalidation reasons*. They intentionally contain
only standard-library types and Pydantic primitives plus the shared common
ID/value types from Task 11 and the artifact hash type from Task 15. No
Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, or any implementation
module is imported, and no raw dataframes, tables, model objects, backend
handles, or large inline payloads are stored.

Scope (Build Queue v2.1 Task 16):

- ``CacheStatus``: stable lifecycle/status enum for a cache entry
  (``hit``, ``miss``, ``stale``, ``invalidated``, ``bypassed``).
- ``InvalidationReasonCode``: stable enum of *why* a cache entry is
  stale/invalid (changed input/config/code/dependency/artifact, missing
  artifact, policy/manual invalidation).
- ``InvalidationReason``: typed, serializable record carrying an
  ``InvalidationReasonCode`` plus optional bounded provenance/metadata.
- ``CacheFingerprint``: typed, serializable fingerprint for
  input/config/code/artifact identity, referencing an ``ArtifactHash``.
- ``CacheKey``: typed, serializable cache key derived from one or more
  ``CacheFingerprint`` entries plus stable common IDs.

Not implemented here:

- Runtime cache storage / cache manager.
- Artifact store behavior (IO/catalog/reporting/registry runtime).
- Manifest writer, registry writer, or pipeline cache behavior.
- Cache key *computation* (hashing scheme) and invalidation *enforcement*.
  These contracts only *represent* keys/fingerprints/status/reasons.

Downstream consumers (artifact store, manifest, registry, pipeline cache)
may import these contracts without pulling runtime or heavy compute
dependencies. The pipeline is the only cross-module orchestrator; domain
modules do not orchestrate each other.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.artifacts import ArtifactHash
from analytics_platform.contracts.common import ArtifactId, RunId, StageId

__all__ = [
    "CacheStatus",
    "InvalidationReasonCode",
    "InvalidationReason",
    "CacheFingerprint",
    "CacheKey",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _CacheContractModel(BaseModel):
    """Base configuration for cache invalidation contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so that the public surface stays explicit and stable
    for downstream consumers. There is deliberately no field for raw
    dataframes, tables, model objects, backend runtime handles, callables,
    sessions, connections, or large inline payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# CacheStatus
# ===========================================================================
class CacheStatus(str, Enum):
    """Lifecycle/status of a cache entry lookup.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries.

    Members:

    - ``HIT``: a valid, fresh cache entry was found.
    - ``MISS``: no cache entry exists for the key.
    - ``STALE``: an entry exists but is stale per invalidation policy.
    - ``INVALIDATED``: an entry was explicitly invalidated (see
      :class:`InvalidationReason`).
    - ``BYPASSED``: cache lookup was bypassed (e.g. policy/runtime flag).
    """

    HIT = "hit"
    MISS = "miss"
    STALE = "stale"
    INVALIDATED = "invalidated"
    BYPASSED = "bypassed"


# ===========================================================================
# InvalidationReason
# ===========================================================================
class InvalidationReasonCode(str, Enum):
    """Stable code describing *why* a cache entry is stale/invalid.

    Values are stable lowercase strings so they serialize deterministically.

    Members:

    - ``CHANGED_INPUT``: input data fingerprint changed.
    - ``CHANGED_CONFIG``: configuration fingerprint changed.
    - ``CHANGED_CODE``: code fingerprint changed.
    - ``CHANGED_DEPENDENCY``: an upstream dependency fingerprint changed.
    - ``CHANGED_ARTIFACT``: a referenced persisted artifact hash changed.
    - ``MISSING_ARTIFACT``: a referenced artifact is missing/unavailable.
    - ``POLICY_INVALIDATION``: invalidated by retention/policy rule.
    - ``MANUAL_INVALIDATION``: invalidated by an explicit operator action.
    """

    CHANGED_INPUT = "changed_input"
    CHANGED_CONFIG = "changed_config"
    CHANGED_CODE = "changed_code"
    CHANGED_DEPENDENCY = "changed_dependency"
    CHANGED_ARTIFACT = "changed_artifact"
    MISSING_ARTIFACT = "missing_artifact"
    POLICY_INVALIDATION = "policy_invalidation"
    MANUAL_INVALIDATION = "manual_invalidation"


class InvalidationReason(_CacheContractModel):
    """A typed, serializable record describing why a cache entry is stale.

    Carries a stable machine-readable ``code`` (an
    :class:`InvalidationReasonCode`) plus optional human-readable ``detail``
    and bounded provenance. It deliberately does not embed raw data, a
    dataframe, a model object, or any large inline payload.

    Fields:

    - ``code``: stable invalidation reason code.
    - ``detail``: optional short human-readable explanation.
    - ``changed_ref``: optional stable reference to the changed/missing input,
      config, code, dependency, or artifact (e.g. an artifact id or label).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    code: InvalidationReasonCode = Field(
        ...,
        description="Stable machine-readable invalidation reason code.",
    )
    detail: str | None = Field(
        default=None,
        max_length=512,
        description="Optional short human-readable explanation of the reason.",
    )
    changed_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional stable reference to the changed/missing input/config/code/dependency/artifact.",
    )
    run_id: RunId | None = Field(
        default=None,
        description="Optional run associated with the invalidation, if any.",
    )
    stage_id: StageId | None = Field(
        default=None,
        description="Optional stage associated with the invalidation, if any.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# CacheFingerprint
# ===========================================================================
class CacheFingerprint(_CacheContractModel):
    """A typed, serializable fingerprint for input/config/code/artifact identity.

    A fingerprint pairs a stable ``kind`` label (e.g. ``"input"``,
    ``"config"``, ``"code"``, ``"dependency"``, ``"artifact"``) with a typed
    :class:`~analytics_platform.contracts.artifacts.ArtifactHash` from Task 15.
    Optional ``label`` and ``source_ref`` provide stable, human-readable
    provenance for the fingerprinted source. It deliberately does not embed
    raw data, a dataframe, a model object, or any large inline payload.

    Fields:

    - ``kind``: stable short label describing what is fingerprinted.
    - ``hash``: typed content-hash representation (reused from Task 15).
    - ``label``: optional short stable human-readable label for the source.
    - ``source_ref``: optional stable reference to the source (e.g. URI/id).
    """

    kind: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable short label describing what is fingerprinted (e.g. 'input', 'config', 'code').",
    )
    hash: ArtifactHash = Field(
        ...,
        description="Typed content-hash representation reused from artifact contracts.",
    )
    label: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short stable human-readable label for the source.",
    )
    source_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional stable reference to the source (e.g. URI/id).",
    )


# ===========================================================================
# CacheKey
# ===========================================================================
class CacheKey(_CacheContractModel):
    """A typed, serializable cache key derived from one or more fingerprints.

    A cache key is composed of a stable ``namespace`` (e.g. stage name or
    cache scope) and an immutable tuple of one or more
    :class:`CacheFingerprint` entries. Comparing keys/fingerprints is how
    downstream cache/manifest/registry code detects that an entry should be
    invalidated (changed input, changed config, changed code, changed
    dependency/artifact, or missing artifact).

    The key carries only stable identifiers and fingerprints; it deliberately
    does not embed raw dataframes, tables, model objects, backend runtime
    handles, callables, sessions, connections, or large inline payloads.
    Cache key *computation* (the exact hashing scheme) and invalidation
    *enforcement* are runtime concerns and are not implemented here.

    Fields:

    - ``namespace``: stable short cache namespace/scope label.
    - ``fingerprints``: immutable tuple of one or more cache fingerprints.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``artifact_id``: optional artifact this cache entry is associated with.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    namespace: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable short cache namespace/scope label (e.g. stage name).",
    )
    fingerprints: tuple[CacheFingerprint, ...] = Field(
        ...,
        min_length=1,
        description="Immutable tuple of one or more cache fingerprints.",
    )
    run_id: RunId | None = Field(
        default=None,
        description="Optional run this cache key is associated with.",
    )
    stage_id: StageId | None = Field(
        default=None,
        description="Optional stage this cache key is associated with.",
    )
    artifact_id: ArtifactId | None = Field(
        default=None,
        description="Optional artifact this cache entry is associated with.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )