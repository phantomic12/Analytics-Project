# Contract Test Plan v1.1

Status: Active for Build Queue v2.1 Task 7.
Owner: Analytics Platform Team.
Scope: documentation-level test strategy for public contracts owned by the
analytics-platform contract families. This plan defines expectations for every
public contract; it does not implement tests yet. Implementation of contract
tests is deferred to later Build Queue v2.1 contract and test tasks.

Companion docs (do not duplicate, refer to them):
- `docs/contracts/contracts-index-v1.1.md` — contract family index.
- `docs/contracts/interface-map-v1.1.md` — stage input/output flow.
- `docs/architecture/dependency-rules-v1.1.md` — import layering.
- `docs/architecture/statistical-validation-strategy-v1.1.md` — claim levels.
- `docs/testing/integration-test-plan-v1.1.md` — integration smoke paths.
- `docs/testing/architecture-test-plan-v1.1.md` — boundary and rule checks.

## 1. Purpose

This document defines what every public contract must satisfy at the test
expectation level, before any contract test is written. It is the
documentation-level source of truth for contract test categories, acceptance
shape, and sequencing. It does not:

- Freeze Pydantic field definitions beyond documentation-level
  responsibilities already present in upstream source docs.
- Introduce implementation code or test files.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Override `dependency-rules-v1.1.md` on import discipline.

If a later contract test task requires a shape incompatible with this plan, the
conflict is resolved by an explicit task that updates this document minimally;
Build Queue v2.1 and actual repo state win.

## 2. Scope of contracts covered

The expectations below apply to every contract family listed in
`docs/contracts/contracts-index-v1.1.md`:

- `common`, `execution`, `artifacts`, `cache`, `visuals`, `datasets`,
  `lineage`, `schemas`, `semantics`, `quality`, `profiling`, `associations`,
  `joins`, `features`, `statistics`, `modeling`, `validation`, `reporting`,
  `registry`, `pipeline`.

Each family is implemented in a later Build Queue v2.1 contract task (Tasks
11–46). This plan applies to a family only once its contract task has produced
the public types. No contract test may be implemented before the contract it
exercises exists.

## 3. Cross-cutting expectations

All public contracts share these test expectations, restated from
`dependency-rules-v1.1.md` and `contracts-index-v1.1.md`:

- Contracts may import `pydantic`, the Python standard library, and other
  contracts only.
- Contracts must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Contracts must not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Contracts must not contain raw dataframe, model, or matrix objects in public
  fields.
- Public objects are typed, serializable, and backend-neutral.
- Every public contract has one request type and/or one result type per stage
  unless explicitly split.
- Skipped and blocked stages are representable as typed `StageResult` records.

## 4. Required test categories

Every public contract type must be covered by expectations in the following
categories. These are expectations only; actual tests are deferred.

### 4.1 Instantiation tests

- Every public contract type can be constructed from its documented required
  fields.
- Optional fields default to documented defaults and never require a heavy
  runtime object.
- Default construction does not perform I/O, does not touch backends, and does
  not materialize dataframes.
- Request/result objects carry only references (`DatasetHandle`,
  `DatasetArtifactRef`, `LazyFrameRef`, `BackendObjectRef`,
  `FeatureMatrixRef`, `ArtifactRef`, `PersistedArtifact`) and never raw
  library objects.
- Enum-like fields accept only documented values.

### 4.2 Invalid-input validation tests

- Missing required fields raise documented validation errors.
- Empty or invalid IDs (`RunId`, `DatasetId`, `ModelId`, `ReportId`,
  `ArtifactId`, `LineageId`, `StageId`) are rejected.
- Invalid enum values are rejected.
- Out-of-range numeric limits (`ExecutionLimitPolicy`,
  `MemoryBudgetPolicy`, `MaterializationPolicy`, `CollectPolicy`,
  `PandasConversionPolicy`) are rejected.
- Invalid join specs (`JoinSpec`, `JoinType`, `JoinCardinality`,
  `JoinRiskLevel`, `JoinApprovalStatus`) are rejected.
- Invalid feature/model specs (`FeatureSpec`, `TargetSpec`, `SplitSpec`,
  `OLSModelSpec`, `ModelSpec`) are rejected with typed reasons.
- Claim-level and causal-policy fields (`ClaimLevel`, `EvidenceGrade`,
  `CausalClaimPolicy`) reject disallowed causal claim levels in MVP output.
- Validation errors are typed and serializable; they never leak exceptions or
  raw library objects.

### 4.3 Serialization round-trip tests

- Every public contract type round-trips through JSON serialization without
  loss of typed information.
- Round-trip preserves enums, optional fields, nested contract objects, and
  reference fields.
- Round-trip does not require importing heavy implementation libraries.
- Timestamps, hashes, and seeds survive round-trip with stable
  representations.
- Deserialization rejects unknown fields unless the contract explicitly allows
  forward-compatible extras.

### 4.4 No raw dataframe/model objects in public contracts

- No public field accepts or returns a Polars, Pandas, DuckDB, NumPy, SciPy,
  Statsmodels, or Matplotlib object.
- Large data is represented only by documented references.
- Model results expose typed summaries (`CoefficientTable`, `ModelCoefficient`,
  `EffectEstimate`, `ConfidenceInterval`, `ModelMetricSet`) and never raw
  Statsmodels objects.
- Feature matrices expose `FeatureMatrixRef`/`FeatureMatrixResult` and never raw
  matrices.
- Execution references expose `LazyFrameRef`/`BackendObjectRef` and never raw
  backend objects.

### 4.5 No heavy implementation imports in contracts

- Contract modules import only `pydantic`, the Python standard library, and
  other contracts.
- Importing a contract module does not transitively import any heavy runtime
  library or any domain implementation.
- This expectation is enforced as a documentation-level contract test category
  here and as an architecture test category in
  `docs/testing/architecture-test-plan-v1.1.md`.

### 4.6 Downstream compatibility tests

- Each contract family is consumable by every documented allowed consumer in
  `contracts-index-v1.1.md` without forcing the consumer to import heavy
  libraries.
- Downstream modules construct request/result objects from documented fields
  only.
- Adding a new optional field to a contract does not break documented
  downstream consumers.
- Removing or renaming a documented public field is a breaking change and
  requires an explicit task that updates this plan and the contracts index
  minimally.

### 4.7 Adjacent-module compatibility tests (documentation-level)

Adjacent modules are those directly connected in the interface map
(`docs/contracts/interface-map-v1.1.md`):

- For each stage, the request type produced by the upstream stage is accepted
  by the downstream stage's request shape, or the mismatch is a documented
  breaking change.
- `StageResult` records from skipped or blocked stages are consumable by
  downstream stages and by reporting without raw data.
- Reporting consumes typed results only and never recomputes analytics.
- Pipeline is the only cross-module orchestrator; domain modules do not call
  each other.
- Adjacent compatibility is documented here as expectations; actual
  adjacent-module tests are deferred to later integration and test tasks and
  must respect Build Queue sequencing.

## 5. Acceptance shape (documentation-level)

A contract family satisfies this plan when, at the documentation level:

1. Every public type in the family maps to at least one expectation in each of
   sections 4.1 through 4.6.
2. Adjacent stages documented in the interface map map to expectations in
   section 4.7.
3. No expectation requires a future-phase module before its prerequisite
   exists.
4. No expectation requires raw dataframes, model objects, or dictionaries in
   public contracts.
5. No expectation requires heavy implementation imports inside contracts.

## 6. Sequencing expectations

Contract test expectations apply family-by-family as Build Queue v2.1 contract
tasks (Tasks 11–46) land each family. In particular:

- `common` (Task 11) must satisfy all categories before any family that
  depends on it is tested.
- Profile-only families (`datasets`, `schemas`, `semantics`, `quality`,
  `profiling`) satisfy expectations before the profile-only MVP checkpoint
  (Task 108).
- Joins, features, modeling, validation, and reporting contract expectations
  apply only once their contract tasks land; this plan does not require them
  earlier.
- Contract test implementation follows Build Queue sequencing and never
  precedes the contract task for a family.

## 7. Out of scope

This plan does not:

- Implement test files or fixtures.
- Freeze Pydantic field shapes beyond documentation-level names.
- Define integration smoke paths (see
  `docs/testing/integration-test-plan-v1.1.md`).
- Define architecture import/file-size rule checks (see
  `docs/testing/architecture-test-plan-v1.1.md`).
- Define performance smoke tests (Task 8 adds the dedicated performance smoke
  test plan).
- Introduce causal claims or statistical findings.

## 8. Documentation-only status

This document is documentation-only. It does not introduce implementation code
or tests. If a later contract test task requires a shape incompatible with this
plan, the conflict is resolved by an explicit task that updates this document
minimally; Build Queue v2.1 and actual repo state win.