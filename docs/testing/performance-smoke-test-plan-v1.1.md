# Performance Smoke Test Plan v1.1

Status: Active for Build Queue v2.1 Task 8.
Owner: Analytics Platform Team.
Scope: documentation-level performance smoke test strategy for the
analytics-platform MVP. This plan defines large-dataset and memory-safety
expectations at smoke-test level; it does not implement tests yet and is not an
exhaustive benchmarking suite. Implementation of performance smoke tests
follows Build Queue v2.1 sequencing.

Companion docs (do not duplicate, refer to them):
- `docs/architecture/dependency-rules-v1.1.md` — import layering.
- `docs/architecture/file-size-rules-v1.1.md` — file-size thresholds.
- `docs/testing/contract-test-plan-v1.1.md` — contract expectations.
- `docs/testing/integration-test-plan-v1.1.md` — integration smoke paths.
- `docs/testing/architecture-test-plan-v1.1.md` — boundary rule checks.

## 1. Purpose

This document is the documentation-level source of truth for performance smoke
expectations: what the MVP must prove about large-dataset handling and
memory safety without becoming a full benchmarking suite. It does not:

- Freeze Pydantic field definitions beyond documentation-level
  responsibilities already present in upstream source docs.
- Introduce implementation code, test files, fixtures, generated datasets,
  generated reports, or artifacts.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Require unbounded materialization or large inline payloads.
- Introduce DuckDB backend implementation or future chart/report artifact
  generation.
- Move performance implementation earlier than its Build Queue schedule.

If a later performance test task requires a shape incompatible with this plan,
the conflict is resolved by an explicit task that updates this document
minimally; Build Queue v2.1 and actual repo state win.

## 2. Cross-cutting performance rules

All performance smoke expectations share these rules, restated from
`dependency-rules-v1.1.md` and the contract testing plan:

- Contracts may import `pydantic`, the Python standard library, and other
  contracts only; they never import heavy runtime libraries.
- No public field accepts or returns a Polars, Pandas, DuckDB, NumPy, SciPy,
  Statsmodels, or Matplotlib object.
- Large data is represented only by documented references
  (`DatasetHandle`, `DatasetArtifactRef`, `LazyFrameRef`, `BackendObjectRef`,
  `FeatureMatrixRef`, `ArtifactRef`, `PersistedArtifact`).
- Pipeline is the only cross-module orchestrator; domain modules do not call
  each other.
- Performance smoke tests validate behavior under documented limits; they are
  not exhaustive benchmarks.
- Synthetic test datasets are used; no real or sensitive datasets.

## 3. Dataset and execution expectations

### 3.1 Large local tabular datasets

- Smoke tests cover large local CSV/Parquet inputs at documented smoke sizes
  only; full benchmarking is out of scope.
- Large datasets are referenced by `DatasetHandle`/`DatasetRef` and never
  embedded in contracts or reports.
- Ingestion produces typed `DatasetLoadResult`/`IngestionReport` and never
  surfaces a raw dataframe publicly.

### 3.2 Polars-first lazy/chunked execution

- Execution is Polars-first and lazy/chunked by default.
- Public results expose `LazyFrameRef`/`BackendObjectRef`, not materialized
  frames.
- Smoke tests assert that lazy plans are built without forcing full
  materialization for the smoke path.

### 3.3 Bounded materialization

- Materialization is bounded by `MaterializationPolicy` and
  `ExecutionLimitPolicy`.
- No public operation requires unbounded materialization.
- Smoke tests assert that bounded materialization respects documented row/column
  limits and produces typed results.

### 3.4 Approximate profiling modes

- Profiling supports approximate modes (`ProfileApproximationMethod`,
  `ProfileComputationMode`) for large datasets.
- Profiles state whether they are exact or approximate.
- Smoke tests assert approximate mode is selected when documented thresholds are
  exceeded and that the profile carries the approximation flag.

### 3.5 Explicit execution limits

- Execution limits (`ExecutionLimitPolicy`, `MemoryBudgetPolicy`,
  `CollectPolicy`, `PandasConversionPolicy`) are explicit and typed.
- Smoke tests assert that exceeding limits produces typed block reasons, not
  silent truncation or crashes.

### 3.6 No unbounded collect operations

- No public path performs an unbounded `collect`.
- Any collect is gated by `CollectPolicy` and `MaterializationPolicy`.
- Smoke tests assert that attempted unbounded collects are blocked or bounded
  with typed reasons.

### 3.7 No large Pandas conversion except bounded private adapter

- Pandas conversion is not part of public contracts.
- A later bounded private modeling adapter (stage 4.19) may perform bounded
  conversion for modeling only; it never exposes raw Pandas/Statsmodels objects
  publicly.
- Smoke tests assert that no large Pandas conversion occurs outside the
  documented bounded private adapter and that the adapter respects limits.

### 3.8 No embedding huge tables, arrays, or datasets

- Contracts and reports never embed huge tables, arrays, matrices, or datasets.
- Reports reference artifacts by `ReportArtifactSet`/artifact refs and never
  inline large payloads.
- Smoke tests assert that report artifacts are referenced, not inlined.

### 3.9 Synthetic test datasets

- Performance smoke tests use synthetic, generated-on-demand datasets only.
- No real or sensitive datasets are used.
- Smoke datasets are sized to exercise limits, not to mirror production scale.

### 3.10 Memory-safety checks

- Smoke tests assert that memory usage stays within `MemoryBudgetPolicy`
  bounds for the smoke path.
- Memory-safety checks verify no unbounded growth during ingestion, profiling,
  joins, feature matrix preparation, and reporting smoke paths.
- Out-of-memory conditions are represented as typed block reasons, not crashes.

### 3.11 Timeout/runtime expectations (smoke, not benchmark)

- Smoke tests define upper-bound runtime expectations for smoke-sized paths
  only.
- Timeouts are documented per smoke path and trigger typed failure behavior,
  not silent hangs.
- These are smoke-level checks, not full benchmarking or regression tracking.

## 4. Smoke path expectations by stage

Each path is documentation-level and sequenced by Build Queue v2.1.

### 4.1 Ingestion smoke

- Assert large local tabular input is ingested via typed requests into a
  `DatasetHandle`/`DatasetRef` without raw dataframes in public output.
- Assert ingestion respects execution limits and produces typed
  `IngestionReport`.

### 4.2 Profiling smoke

- Assert distribution profiling runs in approximate mode when documented
  thresholds are exceeded.
- Assert `DatasetProfile`/`ColumnProfile` carry exact-vs-approximate state and
  no raw frames.

### 4.3 Joins smoke

- Implement only after Task 27 (`joins`) and Task 108 pass.
- Assert join validation/execution stay lazy/bounded and produce typed
  `JoinedDatasetResult`/`JoinExecutionReport` without raw frames.
- Assert unsafe joins are blocked before execution.

### 4.4 Feature matrix preparation smoke

- Implement only after Tasks 28–31 (`features`) pass and after Task 108.
- Assert feature matrix build produces `FeatureMatrixRef`/`FeatureMatrixResult`
  without raw matrices.
- Assert leakage checks block risky paths before modeling.

### 4.5 Reporting smoke

- Assert report generation references artifacts by `ReportArtifactSet` and
  never inlines huge tables/arrays.
- Assert report rendering does not recompute analytics and consumes typed
  results only.

### 4.6 Future backend work (scheduled)

- DuckDB/backend implementation and future chart/report artifact generation are
  scheduled by Build Queue v2.1 and are not implemented in this docs-only task.
- Smoke expectations for backend work apply only once the backend module exists
  and are not pulled forward by this plan.

## 5. Generated artifact/report handling

- Generated artifacts and reports are referenced, not printed in full during
  smoke tests.
- Smoke tests assert artifact existence and reference shape, not large inline
  output.
- Generated files remain exempt from file-size rules per
  `file-size-rules-v1.1.md`.

## 6. Failure behavior when limits exceeded

- When `ExecutionLimitPolicy`, `MemoryBudgetPolicy`, `MaterializationPolicy`,
  or `CollectPolicy` limits would be exceeded, the path must:
  - produce a typed block reason,
  - prevent unbounded materialization or conversion,
  - propagate the block as a skipped/blocked `StageResult` to reporting,
  - never crash or silently truncate.
- Smoke tests assert each failure mode is represented as a typed reason and is
  visible to validation and reporting.

## 7. Acceptance shape (documentation-level)

A performance smoke path satisfies this plan when, at the documentation level:

1. The path uses synthetic datasets and documented smoke sizes only.
2. The path asserts lazy/bounded execution and typed references, not raw
   dataframes/matrices.
3. The path asserts approximate profiling mode selection when thresholds are
   exceeded.
4. The path asserts execution limits produce typed block reasons when
   exceeded.
5. The path asserts no unbounded collect and no large Pandas conversion outside
   the bounded private adapter.
6. The path asserts memory safety and smoke-level timeouts without full
   benchmarking.
7. The path is sequenced after its prerequisite contract tasks and after Task
   108 where applicable.

## 8. Out of scope

This plan does not:

- Implement test files, fixtures, generated datasets, reports, or artifacts.
- Define contract expectations (see
  `docs/testing/contract-test-plan-v1.1.md`).
- Define integration smoke paths (see
  `docs/testing/integration-test-plan-v1.1.md`).
- Define architecture import/file-size rule checks (see
  `docs/testing/architecture-test-plan-v1.1.md`).
- Introduce DuckDB backend implementation or future chart/report artifact
  generation.
- Introduce causal claims or statistical findings.
- Move performance implementation earlier than its Build Queue schedule.

## 9. Documentation-only status

This document is documentation-only. It does not introduce implementation code
or tests. If a later performance test task requires a shape incompatible with
this plan, the conflict is resolved by an explicit task that updates this
document minimally; Build Queue v2.1 and actual repo state win.