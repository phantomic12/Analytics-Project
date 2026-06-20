# Visual Artifact Contracts (v1.1)

**Build Queue reference:** v2.1 Task 17
**Contract module:** `src/analytics_platform/contracts/visuals.py`
**Test module:** `tests/contracts/test_visual_contracts.py`
**Upstream dependencies:** Task 11 (common contracts), Task 15 (artifact persistence contracts)
**Downstream consumers:** Reporting, Registry

## 1. Purpose

This contract family defines **typed references** and **specifications** for future
table and chart artifacts. They are public, typed, serializable, and dependency-light:
downstream consumers (reporting, registry) may import these references without pulling
runtime or heavy compute dependencies (Polars, Pandas, DuckDB, NumPy, SciPy,
Statsmodels, Matplotlib, or any implementation module).

These contracts describe **what** a visual artifact is and **how** it is referenced.
They do **not** describe table generation, chart generation, rendering, Matplotlib
behavior, reporting layout, registry storage, or visual artifact persistence runtime
behavior.

## 2. Public types

All types live in `analytics_platform.contracts.visuals`.

| Type | Kind | Responsibility |
| --- | --- | --- |
| `TableFormat` | Enum | Stable format labels for persisted table artifacts (`csv`, `tsv`, `json`, `parquet`, `markdown`, `html`). |
| `ChartFormat` | Enum | Stable format labels for persisted chart/visual artifacts (`png`, `svg`, `pdf`, `json`). |
| `VisualArtifactRole` | Enum | Advisory role/purpose labels (`summary`, `profile`, `comparison`, `diagnostic`, `report`). |
| `TableArtifactRef` | Model | Typed serializable reference to a persisted table artifact. |
| `ChartArtifactRef` | Model | Typed serializable reference to a persisted chart/visual artifact. |
| `VisualArtifactSpec` | Model | Typed serializable specification/metadata for a visual artifact request or produced visual. |

## 3. Reference fields

`TableArtifactRef` and `ChartArtifactRef` reuse the Task 15 artifact persistence
primitives (`ArtifactHash`, `ArtifactStoragePolicy`) and Task 11 common IDs
(`ArtifactId`, `RunId`, `StageId`). Every visual artifact reference MUST include:

- **artifact_id** — stable artifact identifier.
- **kind** — stable artifact type/kind label (defaults to `table` / `chart`).
- **format** — stable format label (`TableFormat` / `ChartFormat`).
- **location** — stable path or URI-like location of the artifact (no raw payload).
- **hash** — a typed `ArtifactHash` (never raw bytes or image blobs).
- **storage_policy** — an `ArtifactStoragePolicy` inherited from Task 15.
- **producer** / **producer_run_id** / **producer_stage_id** — optional provenance locators.
- **created_at** — optional ISO-8601 creation timestamp.
- **metadata** — small bounded `dict[str, str] | None` metadata (no raw objects).

`TableArtifactRef` additionally carries optional `rows` / `columns` and
`schema_fingerprint`. `ChartArtifactRef` additionally carries optional `mime_type`
and `width_px` / `height_px` descriptors.

`VisualArtifactSpec` ties a request/output to at most one `table_ref` and/or
`chart_ref`, plus `source_artifact_ids`, `role`, `title`, `description`,
`report_id`, and bounded `metadata`. It is a specification only.

## 4. Responsibilities

- Define stable, serializable visual artifact references that downstream consumers use
  to locate, verify, and reason about persisted table/chart artifacts without loading
  their bodies.
- Build on Task 15 artifact persistence contracts (`ArtifactHash`,
  `ArtifactStoragePolicy`) rather than duplicating persistence logic.
- Keep contracts immutable (`frozen=True`) and explicit (`extra="forbid"`).
- Reuse common IDs from Task 11 (`ArtifactId`, `RunId`, `StageId`, `ReportId`).

## 5. Non-scope (explicitly not implemented here)

- **Reporting contracts** — report assembly, layout, and rendering are later tasks.
- **Registry behavior** — visual artifact registry storage/lookup is not implemented here.
- **Chart/table generation** — no Matplotlib, plotting, table rendering, or image
  encoding.
- **Visual artifact persistence runtime behavior** — IO writes, catalog storage,
  registry writes are not implemented here.
- **Dataset, lineage, schema, modeling, validation, and pipeline orchestration**
  contracts.

## 6. Rules against large inline payloads

Visual artifact contracts MUST NOT embed:

- Raw dataframes, tables, arrays, or model objects.
- Raw chart images, binary blobs, or file handles.
- Backend runtime handles, sessions, connections, or callables.
- Large inline byte payloads or generated report contents.

Only stable identifiers, paths/URIs, hashes, policy labels, format labels, small
shape/dimension descriptors, and small bounded string-to-string `metadata` are
permitted. `metadata` is `dict[str, str] | None` and must not carry raw objects.
Unknown fields are rejected at construction (`extra="forbid"`).

## 7. Allowed consumers

Reporting, Registry. These consumers resolve visual artifact references through their
own runtime layers; they do not receive raw tables, chart images, or binary blobs
through these contracts. Domain modules do not orchestrate each other; the pipeline is
the only cross-module orchestrator.

## 8. Dependency rules

- Standard library, Pydantic, common contracts (`analytics_platform.contracts.common`),
  and artifact persistence contracts (`analytics_platform.contracts.artifacts`) only.
- No imports of Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, Matplotlib, or any
  implementation module.
- No import of execution/materialization/cache contracts is required for visual
  artifact contracts. If a future cross-reference is needed, it must remain a typed
  reference, not a runtime object.
- Does not edit `contracts/__init__.py` (Task 46 stabilizes exports later).

## 9. Serialization

All models are Pydantic `BaseModel` subclasses with `frozen=True` and `extra="forbid"`.
Enum values are stable lowercase strings that serialize deterministically across JSON
boundaries. `model_dump(mode="json")` + `model_validate` round-trips are guaranteed by
the contract tests. `source_artifact_ids` is an immutable tuple of `ArtifactId`.

## 10. Verification

Run:

```bash
uv run pytest tests/contracts/test_visual_contracts.py
uv run python -c "from analytics_platform.contracts.visuals import TableArtifactRef, ChartArtifactRef, VisualArtifactSpec; print('visual artifact contracts import ok')"
```
