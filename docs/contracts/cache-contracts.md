# Cache Invalidation Contracts (v1.1)

**Build Queue reference:** v2.1 Task 16
**Contract module:** `src/analytics_platform/contracts/cache.py`
**Test module:** `tests/contracts/test_cache_contracts.py`
**Upstream dependencies:** Task 11 (common contracts), Task 15 (artifact persistence contracts)
**Downstream consumers:** Artifact store, Manifest, Registry, Pipeline cache

## 1. Purpose

This contract family defines **how later runtime/cache, manifest, registry, and
pipeline-cache code may represent cache keys, fingerprints, status, and
invalidation reasons**. They are public, typed, serializable, and
dependency-light: downstream consumers may import these contracts without
pulling runtime or heavy compute dependencies (Polars, Pandas, DuckDB, NumPy,
SciPy, Statsmodels, or any implementation module).

These contracts describe **what** a cache key, fingerprint, status, and
invalidation reason look like. They do **not** describe runtime cache storage, a
cache manager, artifact store behavior, manifest/registry writers, or pipeline
cache behavior. Cache key *computation* (the exact hashing scheme) and
invalidation *enforcement* are runtime concerns and are explicitly out of scope.

## 2. Public types

All types live in `analytics_platform.contracts.cache`.

| Type | Kind | Responsibility |
| --- | --- | --- |
| `CacheStatus` | Enum | Stable lifecycle/status of a cache entry lookup (`hit`, `miss`, `stale`, `invalidated`, `bypassed`). |
| `InvalidationReasonCode` | Enum | Stable code describing *why* a cache entry is stale/invalid. |
| `InvalidationReason` | Model | Typed, serializable record carrying an `InvalidationReasonCode` plus optional bounded provenance/metadata. |
| `CacheFingerprint` | Model | Typed, serializable fingerprint for input/config/code/dependency/artifact identity, referencing an `ArtifactHash`. |
| `CacheKey` | Model | Typed, serializable cache key derived from one or more `CacheFingerprint` entries plus stable common IDs. |

## 3. Cache key / fingerprint responsibilities

A `CacheKey` is composed of:

- A stable short `namespace` label (e.g. stage name or cache scope).
- An immutable tuple of one or more `CacheFingerprint` entries.
- Optional provenance locators (`run_id`, `stage_id`).
- An optional `artifact_id` the cache entry is associated with.
- Small bounded string-to-string `metadata` (no raw objects).

A `CacheFingerprint` pairs:

- A stable short `kind` label (e.g. `"input"`, `"config"`, `"code"`,
  `"dependency"`, `"artifact"`).
- A typed `ArtifactHash` reused from Task 15 (never raw bytes or payloads).
- An optional short stable human-readable `label` for the source.
- An optional stable `source_ref` (e.g. URI or id).

Comparing keys/fingerprints is how downstream cache/manifest/registry code
detects that an entry should be invalidated. The contracts only *represent*
keys and fingerprints; they do not compute or enforce them.

## 4. Invalidation reasons

`InvalidationReasonCode` members (stable lowercase strings):

| Member | Value | Meaning |
| --- | --- | --- |
| `CHANGED_INPUT` | `changed_input` | Input data fingerprint changed. |
| `CHANGED_CONFIG` | `changed_config` | Configuration fingerprint changed. |
| `CHANGED_CODE` | `changed_code` | Code fingerprint changed. |
| `CHANGED_DEPENDENCY` | `changed_dependency` | An upstream dependency fingerprint changed. |
| `CHANGED_ARTIFACT` | `changed_artifact` | A referenced persisted artifact hash changed. |
| `MISSING_ARTIFACT` | `missing_artifact` | A referenced artifact is missing/unavailable. |
| `POLICY_INVALIDATION` | `policy_invalidation` | Invalidated by retention/policy rule. |
| `MANUAL_INVALIDATION` | `manual_invalidation` | Invalidated by an explicit operator action. |

An `InvalidationReason` record carries the `code`, an optional short
human-readable `detail`, an optional stable `changed_ref` pointing to the
changed/missing source, optional `run_id`/`stage_id` provenance, and small
bounded string-to-string `metadata`. It must not embed raw data, a dataframe, a
model object, or any large inline payload.

## 5. Stale artifact policy

A stale or missing artifact is representable through two complementary paths:

1. `CacheStatus.STALE` / `CacheStatus.INVALIDATED` mark the lifecycle state of a
   cache entry lookup.
2. `InvalidationReason` with code `CHANGED_ARTIFACT` or `MISSING_ARTIFACT`
   captures *why* an artifact-dependent entry is stale or invalid, including
   the changed/missing reference via `changed_ref`.

This lets downstream cache/manifest/registry code record both the *status* of a
lookup and the *reason* an entry is no longer usable, without loading artifact
bodies. Changed input, changed config, and changed code hashes are similarly
representable via `CHANGED_INPUT`, `CHANGED_CONFIG`, and `CHANGED_CODE`.

## 6. Non-scope (explicitly not implemented here)

- **Runtime cache storage** / **cache manager**.
- **Artifact store behavior** — IO writes, catalog storage, registry writes,
  reporting rendering.
- **Manifest writer**, **registry writer**, or **pipeline cache** behavior.
- **Cache key computation** (the exact hashing scheme) and **invalidation
  enforcement**. These contracts only *represent* keys/fingerprints/status/reasons.
- **Visual/table/chart** artifact contracts (Task 17).
- **Dataset, lineage, schema, modeling, validation, reporting, registry, and
  pipeline orchestration** contracts.

## 7. Rules against large inline payloads

Cache contracts MUST NOT embed:

- Raw dataframes, tables, arrays, or model objects.
- Backend runtime handles, sessions, connections, or callables.
- Large inline byte payloads or file handles.
- Non-serializable objects.

Only stable identifiers, hashes, fingerprint/kind labels, status/reason codes,
and small bounded string-to-string `metadata` are permitted. `metadata` is
`dict[str, str] | None` and must not carry raw objects. Unknown fields are
rejected at construction (`extra="forbid"`).

## 8. Allowed consumers

Artifact store, Manifest, Registry, Pipeline cache. These consumers resolve
cache keys and fingerprints through their own runtime layers; they do not
receive raw artifact bodies or runtime objects through these contracts. Domain
modules do not orchestrate each other; the pipeline is the only cross-module
orchestrator.

## 9. Dependency rules

- Standard library, Pydantic, common contracts (`analytics_platform.contracts.common`),
  and artifact contracts (`analytics_platform.contracts.artifacts`) only as needed.
- No imports of Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, or any
  implementation module.
- Reuses `ArtifactHash` from Task 15 and `ArtifactId`, `RunId`, `StageId` from
  Task 11 as typed references only.
- Does not edit `contracts/__init__.py` (Task 46 stabilizes exports later).

## 10. Serialization

All models are Pydantic `BaseModel` subclasses with `frozen=True` and
`extra="forbid"`. Enum values are stable lowercase strings that serialize
deterministically across JSON boundaries. `model_dump(mode="json")` +
`model_validate` round-trips are guaranteed by the contract tests.

## 11. Verification

Run:

```bash
uv run pytest tests/contracts/test_cache_contracts.py
uv run python -c "from analytics_platform.contracts.cache import CacheKey, CacheFingerprint, CacheStatus, InvalidationReason; print('cache contracts import ok')"