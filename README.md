# analytics-platform

Reproducible, contract-first analytics platform for large local tabular datasets.

The platform ingests local CSV/Parquet files, validates and profiles them, safely
joins datasets, builds explicit feature matrices, runs OLS/multivariable
regressions, validates outputs, and produces reproducible reports — without
exposing internal dataframes across module boundaries.

## Current status

**Scaffold only.**

This repository currently contains only baseline project files:

- `pyproject.toml` — minimal project metadata (no runtime/dev dependencies yet).
- `.gitignore` — Python/uv/VS Code ignore rules.
- `README.md` — this file.

There is **no implementation code yet**. The `src/analytics_platform/` package,
public contracts, tests, and architecture docs are created by later tasks in the
Build Queue.

## Future package layout

Source will live under:

```
src/analytics_platform/
```

with public contracts under:

```
src/analytics_platform/contracts/
```

Tests will mirror the module layout under `tests/`, and architecture/contract
documentation will live under `docs/`.

## Contract-first workflow

This project follows a strict **contract-first** workflow:

1. **Define public contracts before implementation.** Major stages use a
   `StageRequest -> StageResult` shape. Raw dictionaries are never passed
   across module boundaries unless validated by a typed contract.
2. **Reuse shared types.** Existing contracts are reused for IDs, handles,
   artifacts, cache, execution, lineage, schemas, semantics, quality,
   profiling, joins, features, statistics, modeling, validation, reporting,
   registry, and pipeline. A new data shape is never invented if a shared
   contract/type already exists.
3. **Typed, serializable public outputs.** Public outputs use refs, handles,
   artifacts, and typed summaries — never raw Polars/Pandas/DuckDB/Statsmodels
   objects.
4. **Reporting consumes contracts/results only.** Reports link to artifacts;
   they do not own computation and never recompute analytics.

## Build order

The project follows Build Queue v2.1. The build order is intentionally staged:

1. **Profile-only MVP first.** Local CSV/Parquet ingestion, Polars-backed
   lazy profiling, schema inference/validation, semantic roles, missingness
   and data-quality reports, distribution profiling, diagnostic associations,
   minimal Markdown reporting, manifest, and registry.
2. **Safe joins second.** Join validation and execution happen only after the
   profile-only MVP checkpoint passes.
3. **Feature matrices and modeling last.** Explicit feature matrices, leakage
   checks, OLS fitting, diagnostics, statistical validation, and full reports
   happen only after the profile-only MVP and join prerequisites are satisfied.

No joins, feature/modeling/OLS work, full cache integration, DuckDB backend,
visual/chart generation, or history CLI is implemented before its Build Queue
v2.1 prerequisites are met.

## Tooling

- Python 3.12.x (locked by the project setup).
- `uv` for environment and dependency management.
- Pydantic, Polars, PyArrow, DuckDB (scheduled), Statsmodels, NumPy, SciPy,
  Jinja2, Typer, Rich, pytest, Ruff, a type checker, and Matplotlib (scheduled
  for chart artifacts only).

Full dependency declaration and lock policy are added in Build Queue v2.1
Task 2.
