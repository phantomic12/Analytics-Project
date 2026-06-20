# Artifact Persistence Contracts (v1.1)

**Build Queue reference:** v2.1 Task 15
**Contract module:** `src/analytics_platform/contracts/artifacts.py`
**Test module:** `tests/contracts/test_artifact_contracts.py`
**Upstream dependencies:** Task 11 (common contracts), Task 12 (execution reference contracts), Task 13 (materialization contracts), Task 14 (execution limit contracts)
**Downstream consumers:** IO, Catalog, Reporting, Registry, Cache

## 1. Purpose

This contract family defines **durable artifact references** and a **storage policy**
for persisted pipeline artifacts. They are public, typed, serializable, and
dependency-light: downstream consumers (IO, catalog, reporting, registry, cache)
may import these references without pulling runtime or heavy compute dependencies
(Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, or any implementation module).

These contracts describe **what** an artifact is and **how** it is stored/referenced.
They do **not** describe runtime artifact-writing behavior, backend IO mechanics,
catalog storage, or cache invalidation.

## 2. Public types

All types live in `analytics_platform.contracts.artifacts`.

| Type | Kind | Responsibility |
| --- | --- | --- |
| `ArtifactHashAlgorithm` | Enum | Stable content-hash algorithm labels (`sha256`, `sha1`, `blake3`, `xxhash`, `identity`). |
| `ArtifactHash` | Model | Typed, serializable content-hash representation (algorithm + digest). No raw bytes. |
| `ArtifactStorageMedium` | Enum | Storage medium labels (`local_fs`, `object_store`, `registry`). |
| `ArtifactRetention` | Enum | Retention class labels (`ephemeral`, `run_scoped`, `persistent`). |
| `ArtifactStoragePolicy` | Model | Policy describing how an artifact is stored, retained, and referenced. |
| `PersistedArtifact` | Model | Durable artifact metadata: location, kind, hash, producer/stage metadata, storage policy. |
| `DatasetArtifactRef` | Model | Dataset-specific artifact reference for persisted dataset outputs (e.g. Parquet). |

## 3. Required artifact-ref fields

Every artifact reference (`PersistedArtifact`, `DatasetArtifactRef`) MUST include:

- **path/location** — `location` (path or URI-like string; no raw payload).
- **type/kind** — `kind` (stable artifact type/kind label).
- **hash** — `hash` (a typed `ArtifactHash`, never raw bytes).
- **producer** — `producer`, `producer_run_id`, `producer_stage_id` provenance locators.
- **storage policy** — `storage_policy` (an `ArtifactStoragePolicy`).

`DatasetArtifactRef` additionally carries dataset-specific descriptors:
`dataset_id`, `format`, optional `rows`/`columns`, and optional `schema_fingerprint`.

## 4. Responsibilities

- Define stable, serializable artifact references that downstream consumers use to
  locate, verify, and reason about persisted artifacts without loading artifact bodies.
- Define a storage policy capturing medium, retention, mutability, replication,
  compression, and bounded metadata.
- Keep contracts immutable (`frozen=True`) and explicit (`extra="forbid"`).
- Reuse common IDs from Task 11 (`ArtifactId`, `DatasetId`, `RunId`, `StageId`).

## 5. Non-scope (explicitly not implemented here)

- **Cache invalidation** contracts (Task 16).
- **Visual/table/chart** artifact contracts (Task 17).
- **Artifact store runtime behavior** — IO writes, catalog storage, registry writes,
  reporting rendering, cache reads/writes.
- **Dataset, lineage, schema, modeling, validation, reporting, registry, and pipeline
  orchestration** contracts.
- Backend/materialization runtime mechanics (Tasks 12–14 own execution references and
  materialization policies).

## 6. Rules against large inline payloads

Artifact contracts MUST NOT embed:

- Raw dataframes, tables, arrays, or model objects.
- Backend runtime handles, sessions, connections, or callables.
- Large inline byte payloads or file handles.
- Non-serializable objects.

Only stable identifiers, paths/URIs, hashes, policy labels, and small bounded
string-to-string `metadata` are permitted. `metadata` is `dict[str, str] | None` and
must not carry raw objects. Unknown fields are rejected at construction (`extra="forbid"`).

## 7. Allowed consumers

IO, Catalog, Reporting, Registry, Cache. These consumers resolve artifact references
through their own runtime layers; they do not receive raw artifact bodies through
these contracts. Domain modules do not orchestrate each other; the pipeline is the
only cross-module orchestrator.

## 8. Dependency rules

- Standard library, Pydantic, and common contracts (`analytics_platform.contracts.common`) only.
- No imports of Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, or any implementation module.
- No import of execution/materialization contracts is required for artifact persistence
  contracts. If a future cross-reference is needed, it must remain a typed reference, not
  a runtime object.
- Does not edit `contracts/__init__.py` (Task 46 stabilizes exports later).

## 9. Serialization

All models are Pydantic `BaseModel` subclasses with `frozen=True` and `extra="forbid"`.
Enum values are stable lowercase strings that serialize deterministically across JSON
boundaries. `model_dump(mode="json")` + `model_validate` round-trips are guaranteed by
the contract tests.

## 10. Verification

Run:

```bash
uv run pytest tests/contracts/test_artifact_contracts.py
uv run python -c "from analytics_platform.contracts.artifacts import PersistedArtifact, DatasetArtifactRef, ArtifactStoragePolicy, ArtifactHash; print('artifact contracts import ok')"
```
