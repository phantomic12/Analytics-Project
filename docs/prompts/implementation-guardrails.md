# Implementation Guardrails — GLM/Cline Prompt Rules

Status: Active for Build Queue v2.1 Task 9.
Owner: Analytics Platform Team.
Scope: practical rules for GLM/Cline implementation tasks in the
analytics-platform. Compact prompt guardrail; upstream docs win on conflict.

Companion docs (do not duplicate, refer to them):
- `docs/prompts/stable-cached-context.md` — compact reusable project context.
- `docs/architecture/dependency-rules-v1.1.md` — import layers and forbidden imports.
- `docs/architecture/file-size-rules-v1.1.md` — line-count limits and split rules.
- `docs/testing/*-v1.1.md` — contract, integration, architecture, performance plans.

## 1. Targeted file reading

- Do not scan the whole workspace. Inspect only task-relevant files listed in
  the task prompt.
- For prerequisite docs, prefer existence checks (`test -f …`) unless exact
  source wording is needed.
- If exact wording is needed, use targeted search or headings first, then read
  only the relevant section.
- Do not read, print, diff, or summarize generated/machine-managed files in
  detail unless debugging requires targeted inspection.

## 2. Allowed file scope

- Edit only files explicitly listed as "allowed" in the task prompt.
- Do not modify unrelated files, even for formatting or cleanup.
- If completing the task appears to require editing more than the allowed
  files, stop and propose a narrower split unless Build Queue v2.1 explicitly
  allows the broader scope.

## 3. No unrelated edits

- Do not refactor, rename, or reorganize code outside the task's allowed scope.
- Do not fix pre-existing issues unless the task explicitly authorizes it.
- Do not add convenience helpers, utilities, or fixtures beyond the allowed
  scope.
- Do not touch lockfiles, manifests, generated registries, or artifacts unless
  the task explicitly says so.

## 4. No future-phase implementation

- Do not implement deferred or future-phase modules (`patterns/`,
  `classification.py`, `multiple_testing.py`, `robustness.py`, `scanner.py`,
  database connectors, DuckDB execution backend).
- Deferred dependencies (`duckdb`, `matplotlib`) remain declared for import
  smoke tests only; no behavior is wired in until their Build Queue task.
- Do not pre-import or pre-wire scheduled behavior to make a check pass.

## 5. Source-of-truth preservation

- Preserve existing source-of-truth docs as the source of truth.
- Do not rewrite, truncate, split, or summarize-and-replace them.
- Make only minimal consistency edits required by the explicit task, and only
  within the file's allowed scope.
- Existing source-of-truth docs that exceed the file-size rule are preserved
  unchanged; do not split them solely for line-count compliance.
- If a conflict is found, stop and propose a minimal consistency edit rather
  than rewriting upstream docs from summary.

## 6. Generated-file token discipline

- For generated/machine-managed files (`uv.lock`, lockfiles, generated
  registries/reports/artifacts/metadata, auto-generated `__init__.py`
  re-exports), report only "created" or "updated".
- Do not print, diff, or summarize generated file contents in detail unless a
  task requires targeted inspection for debugging.
- Generated files are exempt from file-size limits unless the task explicitly
  says otherwise.

## 7. File-size limits

For newly created or edited human-authored files (see
`file-size-rules-v1.1.md`):

| Limit | Lines (non-blank, non-comment) | Notes |
| --- | --- | --- |
| Target | 150–300 | Default range to aim for. |
| Soft max | 350 | Review for a split; justify if retained. |
| Hard max | 400 | Do not exceed without a clearly justified reason. |

Split a file when it owns more than one major responsibility, exceeds the soft
maximum, mixes contracts with implementation logic, mixes public API with
private helpers, or duplicates content that has a source-of-truth home
elsewhere. Do not split in ways that create circular imports or move
responsibilities across module boundaries.

## 8. Verification expectations

- Run the verification command specified by the task if available.
- If the shell differs, use an equivalent PowerShell or Python check.
- For prerequisite docs, run existence checks before editing.
- For created/edited prompt docs, run the docs existence check:
  `test -f docs/prompts/<file>.md`.
- Report commands run and results; state any skipped commands and why.

## 9. Response summaries

- Summarize important diffs for human-written files.
- For generated files, say only "created" or "updated" unless debugging
  requires targeted inspection.
- State whether the task is complete, files changed, whether source-of-truth
  docs were preserved, whether targeted file-reading discipline was followed,
  whether generated-file token discipline was followed, and whether the task is
  safe to commit.
- Keep responses compact and reusable.

## 10. Stop-and-ask triggers

Stop and ask, or propose a narrower split, when:
- a prerequisite doc is missing;
- the task requires editing more than the allowed file scope;
- a source-of-truth doc conflicts with the task and cannot be resolved by a
  minimal consistency edit;
- exact source wording is needed but unavailable or ambiguous;
- the task would require pre-implementing future-phase behavior;
- a verification command fails and cannot be resolved within the allowed
  scope.

## 11. Contract-first reminders

- Public contracts are defined before implementations.
- Contracts may import `pydantic`, the standard library, and other contracts only.
- Contracts must not import heavy compute libraries or domain implementations.
- No raw dataframe, model, or matrix objects in public fields.
- Domain modules do not orchestrate each other; only `pipeline` orchestrates.