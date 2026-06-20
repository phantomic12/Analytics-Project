# Dependency Rules v1.1

Status: Active for Build Queue v2.1 Task 4.
Owner: Analytics Platform Team.
Scope: import direction, allowed dependency layers, forbidden imports,
domain module boundaries, contract purity, reporting boundaries, pipeline
orchestration boundaries, the CLI thin-wrapper rule, and source-of-truth
conflict handling for the analytics-platform.

Companion docs (do not duplicate, refer to them):
- `docs/architecture/dependency-policy-v1.1.md` — declared dependencies and
  `uv.lock` policy. This document governs import discipline, not manifest edits.
- `docs/architecture/architecture-pack-v1.1.md` — module inventory and the
  contract-first architecture this document enforces.
- `docs/architecture/quantitative-analysis-design-v1.1.md` — statistical scope
  and claim rules.
- `docs/architecture/file-size-rules-v1.1.md` — file-size limits for the modules
  described here.

## 1. Principles

1. **Contract-first.** Public contracts are defined before implementations and
   import no implementations and no heavy compute libraries.
2. **Layered imports.** Imports point inward and downward: contracts first,
   then core, then domain implementations, then pipeline, then CLI.
3. **No cross-domain orchestration.** Domain modules do not call each other.
   Only `pipeline` sequences stages.
4. **No leaky abstractions.** Raw Polars, Pandas, DuckDB, NumPy, SciPy,
   Statsmodels, and Matplotlib objects never cross public module boundaries.
5. **No future-phase implementation.** Scheduled/deferred dependencies and
   modules are declared for import smoke tests only; their behavior is not
   implemented until their Build Queue v2.1 task is reached.
6. **Source of truth wins.** If this document conflicts with
   `dependency-policy-v1.1.md` or `architecture-pack-v1.1.md`, those upstream
   docs and actual repo state win. This document is then updated by an explicit
   task; it is not silently reinterpreted.

## 2. Dependency layers

Layers are ordered from lowest to highest. Each layer may import only the
layers below it (or peers explicitly allowed here).

| Layer | Path | May import |
| --- | --- | --- |
| contracts | `src/analytics_platform/contracts/` (and shared types modules) | `pydantic`, stdlib, other contracts only |
| core | `src/analytics_platform/core/` | contracts, stdlib |
| domain | `io`, `catalog`, `schema`, `profiling`, `joins`, `features`, `modeling`, `validation` | contracts, core, approved runtime libs in `dependency-policy-v1.1.md` §3 |
| reporting | `src/analytics_platform/reporting/` | contracts only; never domain implementations |
| pipeline | `src/analytics_platform/pipeline/` | contracts, core, domain module public APIs, reporting public APIs |
| cli | `src/analytics_platform/cli/` | contracts, core, pipeline public API only |

## 3. Contract purity

Contracts (`src/analytics_platform/contracts/` and any shared types module):

- May import `pydantic`, the Python standard library, and other contracts.
- Must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Must not import `core`, domain implementations, `reporting`, `pipeline`, or
  `cli`.
- Must not contain raw dataframe, model, or matrix objects in public fields.
- Must not depend on implementation details they describe.

This is the rule most important for later contract tasks: dependency rules
permit contracts to depend only on Pydantic and the standard library.

## 4. Core layer

`src/analytics_platform/core/`:

- May import contracts.
- Must not import domain implementation modules (`io`, `catalog`, `schema`,
  `profiling`, `joins`, `features`, `modeling`, `validation`).
- Must not import `reporting`, `pipeline`, or `cli`.
- Must not perform analytics.
- Owns `AnalysisPlan`, runtime metadata, artifact paths, errors, and logging.

## 5. Domain module boundaries

Each domain module owns one responsibility and exposes typed request/result
contracts. Domain modules:

- May import contracts and core.
- May use the approved runtime libraries in `dependency-policy-v1.1.md` §3
  internally, but must not expose raw library objects publicly.
- Must not import `pipeline` or `cli`.
- Must not import each other. `features` does not import `joins`;
  `validation` does not import `modeling` implementation; `reporting` does not
  import any domain implementation.
- Exchange data only through typed request/result objects, handles, refs, and
  artifacts (`DatasetHandle`, `DatasetRef`, `FeatureMatrixRef`, `ArtifactRef`,
  `LineageRecord`, `StageResult`).
- Must not orchestrate cross-module flows. Cross-domain sequencing is the
  exclusive responsibility of `pipeline`.

Specific clarifications:

- `catalog` owns the private runtime store and maps `DatasetId` to private
  Polars lazy objects; it does not perform analytics.
- `schema` infers and validates schemas; it does not profile distributions.
- `profiling` is descriptive only; no validated findings, no causal language.
- `joins` validates before executing; unsafe joins are blocked by default.
- `features` consumes explicit target/feature specs and blocks leakage by
  default; it does not run models.
- `modeling` consumes `FeatureMatrixResult`, not `DatasetHandle`; it exposes
  typed summaries only, never Statsmodels objects.
- `validation` validates model outputs and enforces claim rules; it does not
  fit models or recompute features.

## 6. Reporting boundaries

`src/analytics_platform/reporting/`:

- Consumes typed results and contracts only (`StageResult`, `ModelResult`,
  `ModelDiagnosticReport`, `ModelValidationReport`, `DatasetProfile`, etc.).
- Must not import domain implementations.
- Must not recompute analytics, refit models, or rescore validation.
- Must not strengthen claim language or drop warnings/limitations.
- Must support skipped stages through the typed `StageResult` records.

## 7. Pipeline orchestration boundaries

`src/analytics_platform/pipeline/`:

- Is the only layer that orchestrates across domain modules.
- Converts `AnalysisPlan` into narrow module request objects.
- Calls domain module public APIs in the correct order.
- Stops or skips stages according to typed stage status.
- Collects stage outputs, writes the run manifest, and returns a typed
  `AnalysisRunResult`.
- Must not embed domain logic; it sequences, it does not compute.

## 8. CLI thin-wrapper rule

`src/analytics_platform/cli/`:

- Is a thin wrapper over `pipeline` and `core` only.
- Does not call domain modules directly.
- Does not contain analytics logic.
- Returns terminal status and artifact paths; it does not return raw library
  objects.

## 9. Forbidden imports

The following imports are forbidden and should be caught by later architecture
tests:

1. Any import of `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
   `statsmodels`, or `matplotlib` from `contracts` or any shared types module.
2. Any import of a domain implementation module from `contracts` or `core`.
3. Any import of `pipeline` or `cli` from a domain module or from `reporting`.
4. Any import of one domain module from another domain module
   (e.g. `features` importing `joins`).
5. Any import of a domain implementation module from `reporting`.
6. Any direct call from `cli` to a domain module.
7. Any import of a future-phase module before its Build Queue task
   (e.g. `patterns`, `classification`, `multiple_testing`, `robustness`).

## 10. Future-phase modules and dependencies

Future-phase modules and deferred dependencies are not implemented early:

- Deferred dependencies (`duckdb`, `matplotlib`) remain declared for import
  smoke tests only; no behavior is wired in until their Build Queue task.
- `pandas` is allowed only as a private, bounded modeling adapter; Pandas types
  must not appear in public contracts, signatures, or return types.
- Removed/future modules (`patterns/`, `classification.py`,
  `multiple_testing.py`, `robustness.py`, `scanner.py`, database connectors)
  must not be created or imported before their task.
- Do not pre-import or pre-wire scheduled behavior to make a check pass.

## 11. Source-of-truth conflict handling

1. `dependency-policy-v1.1.md` is the source of truth for declared dependencies
   and `uv.lock`. This document does not override it.
2. `architecture-pack-v1.1.md` (read with
   `quantitative-analysis-design-v1.1.md`) is the source of truth for module
   inventory and responsibilities. This document restates import rules
   consistent with it; it does not redefine modules.
3. If Build Queue v2.1 conflicts with older docs or local assumptions, Build
   Queue v2.1 and actual repo state win.
4. If a conflict is found, stop and propose a minimal consistency edit rather
   than rewriting upstream docs from summary.
5. Existing source-of-truth docs that exceed the file-size rule are preserved
   unchanged (see `file-size-rules-v1.1.md`).

## 12. Verification

These checks are implemented by later Build Queue tasks (architecture tests)
and are listed here only to define expectations:

- Import boundary tests asserting contracts import no heavy libraries.
- Import boundary tests asserting domain modules do not import each other.
- Import boundary tests asserting `reporting` imports contracts only.
- Import boundary tests asserting `cli` does not call domain modules directly.
- Contract compatibility tests ensuring no contract imports implementation
  modules or heavy compute libraries.