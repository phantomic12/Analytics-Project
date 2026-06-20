# Dependency Policy v1.1

Status: Active for Build Queue v2.1 Task 2.
Owner: Analytics Platform Team.
Scope: this policy governs the dependencies declared in `pyproject.toml` and
locked in `uv.lock` for the analytics-platform MVP and later phases.

## 1. Principles

1. **Contract-first.** Public contracts (`src/analytics_platform/contracts/`)
   must not import heavy implementation libraries. Contracts depend on
   Pydantic and the standard library only.
2. **No leaky abstractions.** Raw Polars, Pandas, DuckDB, NumPy, SciPy,
   Statsmodels, and Matplotlib objects are never returned across module
   boundaries. Public outputs use typed contracts, refs, handles, and
   artifacts.
3. **Boring and reproducible.** Use `uv` for all dependency management. Lower
   bounds are declared in `pyproject.toml`; exact, reproducible versions are
   pinned in `uv.lock`.
4. **Scheduled, not speculative.** Scheduled/deferred dependencies (DuckDB,
   Matplotlib) are declared now so import smoke tests pass, but their behavior
   is not implemented until their Build Queue v2.1 task is reached.
5. **No unscheduled dependencies.** No dependency may be added without an
   explicit task approval that amends this policy and `pyproject.toml` and
   regenerates `uv.lock`.

## 2. Dependency categories

| Category | Declared in | Installed by default |
| --- | --- | --- |
| Runtime/core | `[project] dependencies` | Yes |
| Dev/test/quality | `[dependency-groups] dev` (PEP 735) | Yes (`uv sync`) |

- **Runtime/core** dependencies are required to import and run the platform.
- **Dev/test/quality** dependencies are required to lint, type-check, and test
  the platform. They are not shipped to runtime users.
- There are no hidden optional extras in the MVP. Future extras (for example a
  `duckdb` backend extra) must be added by an explicit task that updates this
  policy.

## 3. Runtime/core dependencies

| Dependency | Lower bound | Why it is present |
| --- | --- | --- |
| `pydantic` | `>=2.5` | Typed, serializable public contracts and shared types. Contracts must not depend on heavy libraries. |
| `polars` | `>=0.20` | Primary lazy dataframe engine for ingestion, profiling, and joins. Never exposed publicly. |
| `pyarrow` | `>=14.0` | Interop layer for Parquet/Arrow IO required by Polars and DuckDB. Never exposed publicly. |
| `duckdb` | `>=0.10` | Scheduled/deferred SQL execution backend. Declared now so import smoke tests pass; not implemented until its Build Queue task. |
| `pandas` | `>=2.1` | Private, bounded modeling adapter only. Never exposed publicly; no public Pandas types. |
| `numpy` | `>=1.26` | Numeric arrays for statistics and modeling. Internal use only. |
| `scipy` | `>=1.11` | Statistical distributions and tests used by diagnostics/validation. Internal use only. |
| `statsmodels` | `>=0.14` | OLS/multivariable regression fitting and diagnostics. Internal use only; no public Statsmodels objects. |
| `jinja2` | `>=3.1` | Templating for Markdown/HTML reports. Reports consume contracts/results only. |
| `typer` | `>=0.9` | CLI layer for the pipeline and history commands. |
| `rich` | `>=13.7` | Terminal output and rendering for CLI and diagnostics. |
| `matplotlib` | `>=3.8` | Scheduled chart artifacts only. Declared now so import smoke tests pass; not implemented until its Build Queue task. |

## 4. Dev/test/quality dependencies

| Dependency | Lower bound | Why it is present |
| --- | --- | --- |
| `pytest` | `>=7.4` | Test runner. `testpaths = ["tests"]`. |
| `ruff` | `>=0.4` | Linter and formatter. Configured under `[tool.ruff]`. |
| `mypy` | `>=1.8` | Type checker. Configured under `[tool.mypy]` in strict mode. |

A type checker is required. `mypy` is the chosen checker; switching to `pyright`
requires an explicit task that updates this policy and `pyproject.toml`.

## 5. `uv` lock policy

1. `uv.lock` is the single source of truth for resolved versions and hashes.
2. `uv.lock` is committed to the repository and tracked (see `.gitignore`).
3. `uv.lock` must be regenerated whenever `pyproject.toml` dependencies or
   dependency groups change:
   ```sh
   uv lock
   ```
4. Environments are created with:
   ```sh
   uv sync
   ```
   which installs runtime dependencies and the `dev` group by default.
5. Lower bounds in `pyproject.toml` must not be widened solely to make a check
   pass. Any constraint change must be justified here and in the task record.
6. Do not hand-edit `uv.lock`. Regenerate it with `uv`.

## 6. Scheduled/deferred dependency limitations

These dependencies are present for import smoke tests and future tasks, but
their behavior is explicitly out of scope until the matching Build Queue task:

- **DuckDB** (`duckdb`): a deferred execution backend. No DuckDB connection,
  query, or backend code is implemented in the MVP. Do not wire DuckDB into the
  pipeline until its task is approved.
- **Pandas** (`pandas`): allowed only as a private, bounded modeling adapter.
  Pandas types must not appear in public contracts, public function signatures,
  or public return types.
- **Matplotlib** (`matplotlib`): reserved for scheduled chart artifacts. No
  chart generation code is added in the MVP; reporting is Markdown-only until
  its task is approved.

## 7. Import discipline

- **Contracts** (`src/analytics_platform/contracts/` and any shared types
  module): may import `pydantic`, the standard library, and other contracts
  only. They must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- **Implementation modules**: may import the approved runtime libraries listed
  in section 3, but must not return raw library objects across module
  boundaries. All public outputs are wrapped in typed contracts, handles, refs,
  or artifacts.
- **Pipeline orchestrates; domain modules do not orchestrate each other.**
  Domain modules expose contracts and implementations; only the pipeline layer
  sequences stages.
- **No causal or statistical overclaims.** Dependencies that compute statistics
  (NumPy, SciPy, Statsmodels) support diagnostics and validation only; their
  outputs are reported with appropriate caveats and never as causal claims.

## 8. Adding or changing dependencies

1. The change must be authorized by an explicit Build Queue task.
2. Update `pyproject.toml` with the lower-bound constraint.
3. Regenerate `uv.lock` with `uv lock`.
4. Update this policy (rationale and limitations).
5. Run the verification commands:
   ```sh
   uv sync
   uv run python -c "import pydantic, polars, pyarrow, duckdb, pandas, numpy, scipy, statsmodels, jinja2, typer, rich, matplotlib, pytest; print('dependency import smoke ok')"
   uv run ruff --version
   uv run mypy --version
   ```
6. Do not weaken constraints to make checks pass without recording the reason.

## 9. Resolved versions (provenance)

The exact versions below were resolved by `uv lock` for Build Queue v2.1 Task 2
on Python 3.12.13 and are pinned in `uv.lock`. They are recorded here for
provenance only; `uv.lock` remains the source of truth. Transitive dependencies
(e.g. `pydantic-core`, `polars-runtime-32`, `markupsafe`) are omitted from this
table and tracked only in `uv.lock`.

### Runtime/core

| Dependency | Resolved version |
| --- | --- |
| `pydantic` | 2.13.4 |
| `polars` | 1.41.2 |
| `pyarrow` | 24.0.0 |
| `duckdb` | 1.5.4 |
| `pandas` | 3.0.3 |
| `numpy` | 2.4.6 |
| `scipy` | 1.18.0 |
| `statsmodels` | 0.14.6 |
| `jinja2` | 3.1.6 |
| `typer` | 0.26.7 |
| `rich` | 15.0.0 |
| `matplotlib` | 3.11.0 |

### Dev/test/quality

| Dependency | Resolved version |
| --- | --- |
| `pytest` | 9.1.1 |
| `ruff` | 0.15.18 |
| `mypy` | 2.1.0 |

### Verification

Task 2 verification was run with `uv 0.11.23` on macOS (aarch64-apple-darwin):

- `uv lock` resolved 45 packages.
- `uv sync` installed 42 packages into `.venv`.
- Dependency import smoke test passed (exit code 0).
- `uv run ruff --version` reported `ruff 0.15.18`.
- `uv run mypy --version` reported `mypy 2.1.0 (compiled: yes)`.
- `uv lock --check` passed (exit code 0).
