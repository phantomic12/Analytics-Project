# Integration Test Plan v1.1

Status: Active for Build Queue v2.1 Task 7.
Owner: Analytics Platform Team.
Scope: documentation-level integration smoke test strategy for the
analytics-platform pipeline. This plan defines integration paths and their
sequencing; it does not implement tests yet. Implementation of integration
tests follows Build Queue v2.1 sequencing.

Companion docs (do not duplicate, refer to them):
- `docs/contracts/contracts-index-v1.1.md` — contract family index.
- `docs/contracts/interface-map-v1.1.md` — canonical stage flow.
- `docs/architecture/architecture-pack-v1.1.md` — module inventory.
- `docs/architecture/statistical-validation-strategy-v1.1.md` — claim levels.
- `docs/testing/contract-test-plan-v1.1.md` — contract expectations.
- `docs/testing/architecture-test-plan-v1.1.md` — boundary rule checks.

## 1. Purpose

This document defines documentation-level integration smoke paths that verify
typed stages compose correctly across module boundaries. It is the
documentation-level source of truth for which integration paths exist, what they
verify, and when they may be implemented. It does not:

- Freeze Pydantic field definitions beyond documentation-level
  responsibilities already present in upstream source docs.
- Introduce implementation code or test files.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Require future-phase modules before their prerequisites exist.
- Move any stage earlier than its Build Queue schedule.

If a later integration test task requires a shape incompatible with this plan,
the conflict is resolved by an explicit task that updates this document
minimally; Build Queue v2.1 and actual repo state win.

## 2. Cross-cutting integration rules

All integration smoke paths share these rules, restated from
`dependency-rules-v1.1.md` and `interface-map-v1.1.md`:

- Pipeline is the only cross-module orchestrator; domain modules do not call
  each other.
- Each stage uses a typed `StageRequest -> StageResult` shape.
- Skipped and blocked stages are represented as typed skipped `StageResult`
  records and are never silently omitted.
- Raw dictionaries, dataframes, model objects, and matrices never cross module
  boundaries.
- Reporting consumes typed results only and never recomputes analytics.
- Causal claims remain blocked in v1.1 MVP output.
- Integration tests do not require a future-phase module before its
  prerequisite contract task lands.

## 3. Sequencing principle

Implementation of integration smoke paths follows Build Queue v2.1 sequencing.
In particular:

- Profile-only paths run before the profile-only MVP checkpoint (Task 108).
- No joins, feature matrices, modeling, full cache integration, chart
  generation, DuckDB implementation, or history CLI integration begins before
  Task 108 passes.
- Each integration path is implemented only after the contracts and stages it
  exercises exist; this plan never moves a path earlier than scheduled.
- Joins, leakage, OLS, cache integration, registry, chart artifacts, and
  performance implementation are scheduled by Build Queue v2.1 and are not
  pulled forward by this plan.

## 4. Profile-only smoke paths

These paths are valid before the profile-only MVP checkpoint. They exercise
typed dataset, schema, semantics, quality, and profiling composition only.

### 4.1 Profile-only end-to-end smoke

- Load a small registered dataset through typed `DatasetLoadRequest`/
  `DatasetLoadResult`.
- Register it to a `DatasetHandle`/`DatasetRef` via
  `RegisteredDatasetResult`.
- Run schema inference to `ObservedSchema`.
- Run semantic role inference to `SemanticTypeInferenceReport`.
- Run schema validation to `SchemaValidationReport`.
- Run data quality/missingness to `DataQualityReport` and `MissingDataReport`.
- Run distribution profiling to `DatasetProfile`/`ColumnProfile`.
- Assert every stage produced a typed `StageResult`; skipped optional stages
  appear as typed skipped records.
- Assert no raw dataframe, dictionary, or model object crossed any boundary.

### 4.2 Profile-only reporting smoke

- Assemble a `ReportInputBundle` from profile-only typed results.
- Render a report to `ReportArtifactSet`.
- Assert the report discloses skipped stages, missingness impact, and claim
  level (non-causal in MVP).
- Assert reporting did not recompute analytics.

## 5. Safe joins smoke

- Implement only after Task 27 (`joins`) and Task 108 pass.
- Submit a `JoinValidationRequest` with a documented safe `JoinSpec`.
- Assert `JoinValidationReport` approves the join.
- Submit `JoinExecutionRequest` against the approved validation.
- Assert `JoinedDatasetResult`, `JoinExecutionReport`, and `LineageRecord`
  are typed and carry no raw dataframe.
- Assert joined dataset re-schema/re-profile/re-quality (stage 4.12) emits
  refreshed typed reports.

## 6. Blocked unsafe joins smoke

- Implement only after Task 27 (`joins`) and Task 108 pass.
- Submit a `JoinValidationRequest` with a documented unsafe `JoinSpec`
  (e.g., high join-induced missingness, risky key compatibility, or blocked
  approval status).
- Assert `JoinValidationReport` blocks the join by default.
- Assert `JoinExecutionRequest` cannot execute without an explicit override
  and that any override is recorded in lineage.
- Assert the block is represented as a typed block reason and propagates as a
  skipped/blocked `StageResult` to reporting.

## 7. Leakage blocking smoke

- Implement only after Tasks 28–31 (`features`) pass and after Task 108.
- Build a feature matrix with a documented leakage risk (e.g., target-as-
  feature, post-outcome predictor, or train/test contamination).
- Assert `LeakageCheckReport` blocks the risky path by default.
- Assert downstream modeling outputs are blocked or downgraded and that the
  block/downgrade is visible to validation and reporting.
- Assert no raw matrix object appears in any public result.

## 8. OLS known-signal / no-signal smoke

- Implement only after Tasks 33–35 (`modeling`) pass and after Task 108.
- Known-signal path: feed a documented synthetic dataset with a known linear
  signal; assert `ModelResult`, `CoefficientTable`, `EffectEstimate`, and
  `ConfidenceInterval` recover the documented direction/level without raw
  Statsmodels objects in public output.
- No-signal path: feed a documented null dataset; assert typed issues
  represent the absence of signal and that claim rules downgrade the
  interpretation rather than emitting unsupported findings.
- Assert causal claim levels remain blocked in MVP output.

## 9. Report generation smoke

- Implement alongside reporting contract tasks (Tasks 39–40) and after Task
  108.
- Assemble `ReportInputBundle` from modeling, validation, and skipped-check
  typed records.
- Render to `ReportArtifactSet`.
- Assert the report includes causal disclaimer, claim level, limitations,
  skipped-check disclosure, missingness impact, join validation status,
  leakage status, and diagnostic status.
- Assert reporting never recomputes analytics and consumes typed results
  only.

## 10. Manifest smoke

- Implement alongside pipeline contract tasks (Tasks 42–45).
- Submit `RunManifestRequest` after a run.
- Assert `RunManifest` references config hash, dataset fingerprints,
  artifacts, and stage statuses.
- Assert skipped and blocked stages appear as typed records in the manifest.

## 11. Registry smoke

- Implement alongside registry contract task (Task 41).
- Submit `RegistryWriteRequest` after manifest writing.
- Assert `RegistryWriteResult` and `RunRegistryRecord` are typed and that
  pipeline owns registry writing; domain modules do not write directly.
- Assert reporting consumes read-only refs only.

## 12. Cache smoke

- Implement alongside cache contract task (Task 16) and full cache integration
  schedule; cache integration is not pulled forward by this plan.
- Assert `CacheKey`/`CacheFingerprint`/`CacheStatus` are typed and that
  invalidation reasons are representable as `InvalidationReason`.
- Assert cache integration does not surface raw artifacts or dataframes in
  public contracts.

## 13. Performance-related paths (scheduled, not implemented here)

- Performance-related integration paths are scheduled by Build Queue v2.1 and
  are not implemented in this docs-only task.
- Task 8 adds the dedicated performance smoke test plan; this plan references
  performance paths as scheduled only and does not define their detailed
  expectations.
- No performance implementation is moved earlier than its Build Queue schedule.

## 14. Acceptance shape (documentation-level)

An integration smoke path satisfies this plan when, at the documentation
level:

1. The path is mapped to one or more typed stages in
   `docs/contracts/interface-map-v1.1.md`.
2. The path asserts typed `StageResult` records for every stage, including
   skipped and blocked ones.
3. The path asserts no raw dataframe, dictionary, model object, or matrix
   crosses any boundary.
4. The path is sequenced after its prerequisite contract tasks and after Task
   108 where applicable.
5. The path does not require a future-phase module before its prerequisite
   exists.

## 15. Out of scope

This plan does not:

- Implement test files or fixtures.
- Freeze Pydantic field shapes beyond documentation-level names.
- Define contract expectations (see
  `docs/testing/contract-test-plan-v1.1.md`).
- Define architecture import/file-size rule checks (see
  `docs/testing/architecture-test-plan-v1.1.md`).
- Define detailed performance smoke test expectations (Task 8 owns these).
- Move joins, leakage, OLS, cache integration, registry, chart artifacts, or
  performance implementation earlier than scheduled.
- Introduce causal claims or statistical findings.

## 16. Documentation-only status

This document is documentation-only. It does not introduce implementation code
or tests. If a later integration test task requires a shape incompatible with
this plan, the conflict is resolved by an explicit task that updates this
document minimally; Build Queue v2.1 and actual repo state win.