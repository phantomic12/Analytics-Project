# File-Size Rules v1.1

Status: Active for Build Queue v2.1 Task 4.
Owner: Analytics Platform Team.
Scope: file-size limits for human-authored source and documentation files in
the analytics-platform, including when to split files, how to keep modules
narrow, exemptions for generated files, the special preservation rule for
existing source-of-truth docs, and how GLM/Cline should stop instead of
editing broadly.

Companion docs:
- `docs/architecture/dependency-rules-v1.1.md` — import and modularity rules
  for the modules these limits apply to.
- `docs/architecture/dependency-policy-v1.1.md` — declared dependencies.
- `docs/architecture/architecture-pack-v1.1.md` — module inventory.

## 1. Principles

1. **Narrow files.** Human-authored files should each own one responsibility
   and be easy to review in a single screen.
2. **Soft before hard.** Prefer splitting at the soft maximum before reaching
   the hard maximum.
3. **Preserve source-of-truth docs.** Existing source-of-truth docs that exceed
   the limits are preserved, not truncated or split solely for line-count
   compliance.
4. **Generated files are exempt.** Lockfiles, registries, reports, artifacts,
  and metadata are not bound by these limits.
5. **Stop instead of broad edits.** If a task would require editing more files
   than its allowed scope, stop and propose a narrower split.

## 2. Line-count limits

For newly created or edited human-authored files:

| Limit | Lines (excluding blank lines and comments) | Notes |
| --- | --- | --- |
| Target | 150–300 | Default range to aim for. |
| Soft max | 350 | Review for a split; justify if retained. |
| Hard max | 400 | Do not exceed without a clearly justified reason recorded in the file or task. |

Unless a task specifies otherwise, line counts refer to non-blank,
non-comment source lines. For Markdown, count rendered prose and code blocks;
do not pad with blank lines to meet a target.

## 3. When to split a file

Split a human-authored file when any of the following is true:

1. It owns more than one major responsibility (e.g., two domain concerns).
2. It exceeds the soft maximum of 350 lines.
3. It mixes contract definitions with implementation logic.
4. It mixes public API with private helpers that could move to a sibling module.
5. It duplicates content that already has a source-of-truth home elsewhere.

Preferred split strategies, in order:

1. Move contract types into `contracts/` and implementations into the
   matching domain module.
2. Move private helpers into a sibling `_internal` or helper module that is not
   imported across module boundaries.
3. Split by stage or concern (e.g., `joins/validator.py` vs.
   `joins/executor.py`).
4. Extract large documentation sections into their own doc files, keeping
   cross-references.

Do not split in ways that:

- Create circular imports.
- Move responsibilities across module boundaries defined in
  `dependency-rules-v1.1.md`.
- Fragment a single contract into multiple files when one file would do.

## 4. Keeping modules narrow

- Each module should map to one architectural responsibility from
  `architecture-pack-v1.1.md` §5.
- Public request/result types live in `contracts/`; implementations live in
  the domain module.
- Avoid god objects: `pipeline` orchestrates only; it does not compute.
- Avoid mega-files: a module with `__init__.py`, one public module, and a few
  narrow helpers is preferred over a single large file.
- Prefer small, focused test files per module over one large test file.

## 5. Generated-file exemptions

The following are exempt from these limits unless a task explicitly says
otherwise:

- `uv.lock` and any lockfile.
- Dependency manifests such as `pyproject.toml` (configuration, not prose).
- Generated registries, indexes, reports, and artifacts.
- Serialized metadata, manifests, and machine-managed files.
- Auto-generated `__init__.py` re-exports when produced by a tool.

For generated files, GLM/Cline should report only "created" or "updated"
unless a task requires targeted inspection for debugging.

## 6. Existing source-of-truth docs

Special preservation rule:

- Existing source-of-truth docs that exceed the hard maximum are preserved
  unchanged.
- Do not rewrite, truncate, or split them solely for line-count compliance.
- Do not summarize-and-replace them.
- Make only minimal consistency edits required by an explicit task, and only
  within the file's allowed scope.

Examples in this repo (non-exhaustive, determined by status lines and
ownership):

- `docs/architecture/architecture-pack-v1.1.md`
- `docs/architecture/quantitative-analysis-design-v1.1.md`
- `docs/architecture/dependency-policy-v1.1.md`

These are upstream source-of-truth docs for Task 4. They are not edited here
and are not split to satisfy this rule.

## 7. Stop-instead-of-broad-edits

GLM/Cline must stop and propose a narrower split rather than:

1. Editing more files than the task's allowed scope permits.
2. Rewriting an upstream source-of-truth doc from summary.
3. Splitting a source-of-truth doc solely for line-count compliance.
4. Adding implementation code, public contracts, or shared types when a task
   only asks for rules docs.
5. Pre-implementing future-phase modules to "fix" a file-size limit.

If a task appears to require any of the above, the correct action is to stop
and describe the narrower change needed.

## 8. Verification

These checks are implemented by later Build Queue tasks and are listed here
only to define expectations:

- A check that newly created or edited human-authored files fall within
  150–400 lines, with soft-max reviewers.
- A check that generated files are exempt.
- A check that existing source-of-truth docs are not truncated or split solely
  for line-count compliance.