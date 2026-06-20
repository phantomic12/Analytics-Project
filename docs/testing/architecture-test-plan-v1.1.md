# Architecture Test Plan v1.1

Status: Active for Build Queue v2.1 Task 7.
Owner: Analytics Platform Team.
Scope: documentation-level architecture test strategy for the
analytics-platform. This plan defines expectations for boundary and rule
checks that enforce dependency rules and file-size rules; it does not
implement tests yet. Architecture tests enforce dependency rules and file-size
rules later, not in this docs-only task.

Companion docs (do not duplicate, refer to them):
- `docs/architecture/dependency-rules-v1.1.md` — import layering and forbidden
  imports.
- `docs/architecture/file-size-rules-v1.1.md` — file-size thresholds.
- `docs/architecture/architecture-pack-v1.1.md` — module inventory.
- `docs/contracts/contracts-index-v1.1.md` — contract family index.
- `docs/contracts/interface-map-v1.1.md` — stage flow and orchestrator rules.
- `docs/testing/contract-test-plan-v1.1.md` — contract expectations.

## 1. Purpose

This document defines documentation-level architecture test expectations that
keep the codebase within the contract-first boundary rules. It is the
documentation-level source of truth for which boundary and rule checks exist and
what they enforce. It does not:

- Freeze import rules beyond `dependency-rules-v1.1.md`.
- Freeze file-size thresholds beyond `file-size-rules-v1.1.md`.
- Introduce implementation code or test files.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Move enforcement earlier than Build Queue v2.1 schedule.

If a later architecture test task requires a shape incompatible with this plan,
the conflict is resolved by an explicit task that updates this document
minimally; Build Queue v2.1 and actual repo state win.

## 2. Cross-cutting architecture rules

All architecture test expectations share these rules, restated from
`dependency-rules-v1.1.md`, `file-size-rules-v1.1.md`, and
`contracts-index-v1.1.md`:

- Contracts may import `pydantic`, the Python standard library, and other
  contracts only.
- Contracts must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Contracts must not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Pipeline is the only cross-module orchestrator; domain modules do not call
  each other.
- Reporting consumes contracts/results only and never imports domain
  implementations.
- Domain modules do not import `contracts/pipeline.py`.
- No raw dataframes, model objects, or dictionaries in public fields.
- File sizes follow `file-size-rules-v1.1.md` (target 150–300 lines, soft max
  350, hard max 400 unless justified).
- Generated files are exempt from file-size rules unless explicitly stated.

## 3. Required test categories

The following categories define architecture test expectations. They are
expectations only; actual tests are deferred.

### 3.1 Import boundary tests

- Each module imports only its documented allowed dependencies.
- Domain modules import contracts and their own internals only; they do not
  import sibling domain modules.
- `reporting` imports contracts only and never domain implementations.
- `cli` is a thin wrapper and does not call domain modules directly; it goes
  through the pipeline.
- `pipeline` is the only module that orchestrates across domain modules.
- No module imports a heavy runtime library into a contract module
  transitively.

### 3.2 Contracts-do-not-import-implementations tests

- Contract modules import only `pydantic`, the Python standard library, and
  other contracts.
- Contract modules do not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Contract modules do not import `polars`, `pandas`, `duckdb`, `numpy`,
  `scipy`, `statsmodels`, or `matplotlib`.
- Importing any contract module does not transitively import any heavy runtime
  library or domain implementation.
- This category is the architecture-level counterpart of the contract test
  category in `docs/testing/contract-test-plan-v1.1.md` section 4.5.

### 3.3 File-size rule checks

- Human-authored source files remain within `file-size-rules-v1.1.md`
  thresholds: target 150–300 lines, soft max 350, hard max 400 unless clearly
  justified.
- Generated files (e.g., `uv.lock`, lockfiles, generated registries,
  generated reports, generated artifacts, generated metadata) are exempt
  unless explicitly stated.
- Existing source-of-truth docs that exceed thresholds are preserved and are
  not flagged for truncation, rewriting, or splitting solely for line-count
  compliance.

### 3.4 Reporting boundary checks

- `reporting` imports contracts only.
- `reporting` never recomputes analytics.
- `reporting` consumes typed `StageResult`/result contracts only and never raw
  dataframes, model objects, matrices, or dictionaries.
- Report rendering produces `ReportArtifactSet` from `ReportInputBundle`/
  `ReportSection` typed inputs.
- Skipped and blocked stages appear as typed skipped records in reports.

### 3.5 Domain/pipeline boundary checks

- Pipeline is the only cross-module orchestrator.
- Domain modules do not call each other directly.
- Domain modules do not import `contracts/pipeline.py`.
- Pipeline calls domain modules through their documented request/result
  contracts.
- Registry writing is owned by pipeline; domain modules do not write directly.

### 3.6 CLI thin-wrapper checks

- `cli` imports pipeline/contracts only and does not call domain modules
  directly.
- `cli` produces terminal status and artifact paths from `AnalysisRunResult`
  only.
- `cli` does not perform analytics or import heavy runtime libraries beyond
  what the pipeline exposes through typed results.

### 3.7 Generated-file handling expectations

- Generated files (e.g., `uv.lock`, package lockfiles, generated registries,
  generated reports, generated artifacts, generated metadata, large
  auto-generated outputs) are exempt from import and file-size architecture
  rules unless explicitly stated.
- Architecture tests must not fail on generated files solely for line-count
  reasons.
- Architecture tests may, where relevant, assert that generated files are not
  imported as source by human-authored modules.

## 4. Acceptance shape (documentation-level)

An architecture test category satisfies this plan when, at the documentation
level:

1. The category maps to one or more rules in
   `dependency-rules-v1.1.md` or `file-size-rules-v1.1.md`.
2. The category is enforceable statically (import graph and file sizes) without
   running analytics.
3. The category exempts generated files unless explicitly stated.
4. The category preserves existing source-of-truth docs that exceed file-size
   thresholds.
5. The category does not require a future-phase module before its prerequisite
   exists.

## 5. Sequencing expectations

Architecture test implementation follows Build Queue v2.1 sequencing:

- Import boundary and contracts-do-not-import-implementations checks may be
  implemented once the first contract tasks land; they are not required before
  contracts exist.
- File-size rule checks may run continuously once the rule set is active.
- Reporting boundary, domain/pipeline boundary, and CLI thin-wrapper checks
  apply once their modules exist and are not pulled forward by this plan.
- Enforcement of dependency rules and file-size rules happens later, not in
  this docs-only task.

## 6. Out of scope

This plan does not:

- Implement test files or fixtures.
- Freeze import rules beyond `dependency-rules-v1.1.md`.
- Freeze file-size thresholds beyond `file-size-rules-v1.1.md`.
- Define contract expectations (see
  `docs/testing/contract-test-plan-v1.1.md`).
- Define integration smoke paths (see
  `docs/testing/integration-test-plan-v1.1.md`).
- Define performance smoke tests (Task 8 owns these).
- Introduce causal claims or statistical findings.

## 7. Documentation-only status

This document is documentation-only. It does not introduce implementation code
or tests. If a later architecture test task requires a shape incompatible with
this plan, the conflict is resolved by an explicit task that updates this
document minimally; Build Queue v2.1 and actual repo state win.