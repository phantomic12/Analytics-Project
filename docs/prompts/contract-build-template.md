# Contract Build Template — GLM/Cline Prompt Template

Status: Active for Build Queue v2.1 Task 9.
Owner: Analytics Platform Team.
Scope: reusable template for future public contract tasks in the
analytics-platform. Compact prompt guardrail; upstream docs win on conflict.

Companion docs (do not duplicate, refer to them):
- `docs/prompts/stable-cached-context.md` — compact reusable project context.
- `docs/prompts/implementation-guardrails.md` — practical implementation rules.
- `docs/contracts/contracts-index-v1.1.md` — contract families and sequencing.
- `docs/contracts/interface-map-v1.1.md` — stage request/result flow.
- `docs/architecture/dependency-rules-v1.1.md` — import layers and forbidden imports.
- `docs/architecture/file-size-rules-v1.1.md` — line-count limits and split rules.
- `docs/testing/contract-test-plan-v1.1.md` — contract test categories.

## 1. Task number/name

- Build Queue v2.1 Task: `<task number>` — `<contract family>`.
- Contract family (from `contracts-index-v1.1.md` §3): `<family>`.
- Intended module: `src/analytics_platform/contracts/<file>.py`.
- Owned concepts: `<list the types/enums this family owns>`.

## 2. Allowed files

- List every file the task is permitted to create or edit.
- Do not edit files outside this list. If more files appear necessary, stop
  and propose a narrower split.

## 3. Public types

- Enumerate the public Pydantic models and enums to be defined.
- Note any types imported from earlier contract families (e.g., `common.py`
  base IDs, `StageResult`, `ArtifactRef`).
- Note any types re-exported through `contracts/__init__.py` (if that file is
  in the allowed scope).

## 4. Upstream dependencies

- Build Queue tasks that must already be complete (existence-check their
  docs/outputs).
- Earlier contract families this family imports (e.g., `common`, `datasets`).

## 5. Downstream consumers affected

- Domain modules and other contract families that will import this family
  (from `contracts-index-v1.1.md` §3 "Allowed consumers").

## 6. Implementation instructions

- Define contracts before any implementation that consumes them.
- Use Pydantic models and enums; keep fields typed and serializable.
- Do not paste architecture-doc text into code; restate only what is required.
- Make only minimal consistency edits to source-of-truth docs if required by
  the task; otherwise do not edit them.
- Preserve existing docs that exceed the file-size rule.

## 7. Test requirements

From `contract-test-plan-v1.1.md`, required categories include:
- Instantiation tests for every public type.
- Invalid-input validation tests (constraints raise `ValidationError`).
- Serialization round-trip tests (model_dump/model_validate_json or
  equivalent).
- No raw dataframe/model objects in public contracts (static/structural).
- No heavy implementation imports in contracts (static/structural).
- Downstream/adjacent compatibility tests (documentation-level where the
  consumer does not exist yet).
- Run the verification command(s) specified by the task.

## 8. Serialization and invalid-input checks

- Every public model must round-trip through serialization without loss.
- Invalid inputs (missing required fields, wrong types, out-of-range enum
  values) must raise typed validation errors.
- Optional fields must have explicit defaults or be explicitly optional.
- No silent coercion that hides invalid data.

## 9. Dependency/import constraints

- Contracts may import `pydantic`, the standard library, and other contracts only.
- Contracts must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Contracts must not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Domain modules do not import `contracts/pipeline.py`.
- No raw dataframe, model, or matrix objects in public fields.
- Public objects are typed, serializable, and backend-neutral.

## 10. File-size rules

- Target 150–300 lines per newly created/edited human-authored file.
- Soft max 350; hard max 400 (justify if exceeded).
- Generated files are exempt.
- Existing source-of-truth docs that exceed the limit are preserved unchanged.
- Split by contract family or concern; do not fragment a single contract into
  multiple files when one file would do.

## 11. Contract shape rules (reminder)

- Contracts must be typed, serializable, and Pydantic-based where appropriate.
- Contracts must not expose raw dataframe/model objects.
- Contracts must not import heavy implementation libraries.
- A concept is never invented in a second family if it already has a home in
  `contracts-index-v1.1.md`.
- Causal claim levels remain blocked in v1.1 MVP output; validation/reporting
  contracts must enforce claim rules consistent with
  `statistical-validation-strategy-v1.1.md`.

## 12. Response format

- State whether the task is complete.
- List files changed.
- Summarize important diffs for human-written files; say only "created" or
  "updated" for generated files unless debugging requires targeted inspection.
- State whether existing source-of-truth docs were preserved.
- List commands run and results; state any skipped commands and why.
- State whether targeted file-reading discipline and generated-file token
  discipline were followed.
- State whether the task is safe to commit.
- Expected Git commit message format: `Add <contract family> contracts`.

## 13. Stop-and-ask triggers

Stop and ask, or propose a narrower split, when:
- a prerequisite task or doc is missing;
- the contract shape conflicts with `contracts-index-v1.1.md` and cannot be
  resolved by a minimal consistency edit;
- exact source wording from upstream docs is needed but unavailable or
  ambiguous;
- the task requires editing files outside the allowed scope;
- the task would require importing a heavy library or domain implementation
  into a contract.