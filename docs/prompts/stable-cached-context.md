# Stable Cached Context — GLM/Cline Prompt Guardrails

Status: Active for Build Queue v2.1 Task 9.
Owner: Analytics Platform Team.
Scope: compact reusable context for GLM/Cline tasks in the analytics-platform.
This file is a cached prompt context, not an architecture source of truth. It
restates upstream rules in compact form; upstream docs win on conflict.

Companion source-of-truth docs (do not duplicate, refer to them):
- `docs/architecture/architecture-pack-v1.1.md` — product scope, MVP, tech stack, module inventory.
- `docs/architecture/quantitative-analysis-design-v1.1.md` — v1.1 quantitative contract additions.
- `docs/architecture/dependency-rules-v1.1.md` — import layers and forbidden imports.
- `docs/architecture/file-size-rules-v1.1.md` — line-count limits and split rules.
- `docs/architecture/statistical-validation-strategy-v1.1.md` — claim levels and validation doctrine.
- `docs/contracts/contracts-index-v1.1.md` — contract families and sequencing.
- `docs/contracts/interface-map-v1.1.md` — stage request/result flow.
- `docs/testing/*-v1.1.md` — contract, integration, architecture, performance plans.

## 1. Project purpose

Build a Python analytics platform that processes tabular datasets through a
reproducible, validated analytical workflow: ingestion, profiling, safe joins,
regression/modeling, statistical validation, and reproducible reporting.

The first implementation version is boring, reliable, contract-first, testable,
and statistically conservative. It proves the foundation without trying to
automate all insight discovery.

## 2. MVP scope

v1 MVP includes: local CSV/Parquet ingestion; dataset registration; schema
inference and optional expected-schema validation; dataset profiling; safe
join validation and execution; OLS regression only; basic feature matrix
preparation for OLS; leakage checks for target and obvious post-outcome
features; regression diagnostics; statistical validation of model outputs;
Markdown report generation (HTML if simple); run manifest; CLI to run an
analysis from config; contract tests; integration smoke tests.

## 3. MVP non-scope

Out of v1 MVP: broad automatic pattern scanning; logistic regression;
classification; scikit-learn model training; cross-validation; hyperparameter
tuning; advanced feature engineering; time-series modeling; causal inference;
dashboard UI; PDF export; database connectors; cloud execution; multi-user
support; LLM-generated findings; automatic data cleaning; complex missingness
imputation; distributed execution.

Do not pre-implement deferred or future-phase modules (`patterns/`,
`classification.py`, `multiple_testing.py`, `robustness.py`, `scanner.py`,
database connectors). DuckDB is deferred and remains declared for import smoke
tests only.

## 4. Tech stack

Required v1: Python 3.12.13, `uv`, Pydantic, Polars, PyArrow, Statsmodels,
NumPy, SciPy, Jinja2, Typer, Rich, Pytest, Ruff, Mypy/Pyright.

Deferred: DuckDB, scikit-learn, Pandera, PDF rendering, dashboard tools, cloud
libraries.

Polars is the default local dataframe engine. Pandas may be used only as a
private, bounded modeling conversion layer; Pandas objects must not cross
public module boundaries.

## 5. Repo conventions

Contract-first layout under `src/analytics_platform/`:
`contracts/`, `core/`, `io/`, `catalog/`, `schema/`, `profiling/`, `joins/`,
`features/`, `modeling/`, `validation/`, `reporting/`, `pipeline/`, `cli/`.
Tests live under `tests/` (`contracts/`, `unit/`, `integration/`,
`architecture/`, `fixtures/`). Docs live under `docs/`.

Stable cross-module reference objects: `DatasetHandle`, `DatasetRef`,
`FeatureMatrixRef`, `ArtifactRef`, `LineageRecord`, `StageResult`. Heavy
runtime objects stay private.

## 6. Contract-first rules

- Public contracts are defined before implementations.
- Contracts may import `pydantic`, the standard library, and other contracts only.
- Contracts must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Contracts must not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Public objects are typed, serializable, and backend-neutral.
- No raw dataframe, model, or matrix objects in public fields.

## 7. Dependency/import rules

Layers, lowest to highest: `contracts` → `core` → domain (`io`, `catalog`,
`schema`, `profiling`, `joins`, `features`, `modeling`, `validation`) →
`reporting` → `pipeline` → `cli`. Imports point inward and downward.

- Domain modules do not import each other. Only `pipeline` orchestrates across
  domain modules.
- `reporting` imports contracts only, never domain implementations, and never
  recomputes analytics.
- `cli` is a thin wrapper over `pipeline` and `core`; it does not call domain
  modules directly.
- Future-phase modules must not be created or imported before their Build Queue
  task.

## 8. Testing rules

Required test categories include: contract instantiation; invalid-input
validation; serialization round trips; no raw dataframe/model objects in public
contracts; no heavy implementation imports in contracts; downstream/adjacent
compatibility; import boundary tests; file-size rule checks; reporting
boundary checks; pipeline/domain boundary checks; CLI thin-wrapper checks; and
a million-row performance smoke test (not a full benchmark).

Tests use synthetic known-answer datasets. Architecture tests enforce
forbidden imports and file-size limits.

## 9. Statistical validity rules

- Claim levels in MVP: `DESCRIPTIVE`, `DIAGNOSTIC`, `ASSOCIATIONAL`,
  `PREDICTIVE_LIMITED`. Disallowed: `CAUSAL`, `EFFECT_CAUSAL`,
  `POLICY_ACTIONABLE`, and any intervention/counterfactual claim.
- Causal language is blocked entirely in v1.1 MVP.
- A p-value alone is never sufficient evidence. Required evidence for
  associational/predictive outputs: effect size; confidence interval where
  available; sample size; sample-to-feature ratio; diagnostic status;
  missingness summary; interpretation limits; multiple-testing context.
- Outputs are classified `DESCRIPTIVE`, `DIAGNOSTIC`, `ASSOCIATIONAL`,
  `PREDICTIVE_LIMITED`, `UNSUPPORTED`, or `BLOCKED`. Every block produces a
  typed block reason; every downgrade is recorded; every warning is visible.
- Leakage checks are mandatory and blocking by default. Joins are
  validation-sensitive and unsafe joins are blocked by default.

## 10. Data safety rules

- No raw Polars/Pandas/DuckDB/NumPy/SciPy/Statsmodels/Matplotlib objects cross
  public module boundaries.
- Modeling consumes `FeatureMatrixResult`, not `DatasetHandle`.
- Fitted preprocessing is applied only after train/test split.
- Severe missingness, join issues, leakage, and invalid model specs must block
  or downgrade, never silently promote.

## 11. Performance rules

- Polars lazy execution is the default; no accidental full Pandas loads.
- No unbounded `collect`; bounded materialization and explicit execution limits.
- Approximate profiling modes for large datasets.
- No large Pandas conversion except a bounded private modeling adapter.
- No embedding huge tables/arrays/datasets in contracts or reports.
- Modeling has explicit row limits and sampling policy.

## 12. Artifact/cache/reproducibility rules

- Run manifest records stage outputs and typed `StageResult` records.
- Artifacts are referenced through typed `ArtifactRef` and persist via
  `contracts/artifacts.py` and `contracts/cache.py` policies.
- Skipped checks are emitted as typed skipped records, never omitted silently.
- Reports must not imply stability when no robustness checks were performed.

## 13. GLM response rules

- Preserve source-of-truth docs; do not rewrite them from summary.
- Make only minimal consistency edits within the allowed file scope.
- Do not implement code, public contracts, or future-phase modules unless the
  task explicitly authorizes it.
- Summarize important diffs for human-written files; report only "created" or
  "updated" for generated files unless targeted debugging is required.
- Keep responses compact and reusable.

## 14. Stop-and-ask rules

Stop and ask, or propose a narrower split, when:
- a prerequisite doc is missing;
- the task appears to require editing more than the allowed files;
- a source-of-truth doc conflicts with the task and the conflict cannot be
  resolved by a minimal consistency edit;
- exact source wording is needed but unavailable or ambiguous;
- the task would require pre-implementing future-phase behavior.

## 15. Build-order guardrails

- Follow Build Queue v2.1 task ordering. Do not start a task before its
  prerequisites exist.
- The profile-only MVP checkpoint is Task 108: no joins, feature matrices,
  modeling, full cache integration, chart generation, DuckDB implementation, or
  history CLI begins before Task 108 passes.
- If older docs conflict with Build Queue v2.1 or actual repo state, Build
  Queue v2.1 and repo state win.