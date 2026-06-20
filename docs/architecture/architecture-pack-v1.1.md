This document is Architecture Pack v1, treated as v1.1 when read together with quantitative-analysis-design-v1.1.md.
# Architecture Pack v1 — Python Analytics Platform

## 0. Purpose of v1

Architecture Pack v1 revises Architecture Pack v0 and the Contract-First Interface Map v0 after a skeptical senior engineering and statistical methods review.

The original project goal is preserved:

> Build a Python-based analytics platform that can ingest large tabular datasets, profile them, join datasets, run regressions and multivariable models, detect patterns, validate those patterns, and produce reproducible reports.

However, v1 tightens the first version to avoid overengineering, ambiguous contracts, circular dependencies, statistical overclaiming, and AI-assisted coding confusion.

The first implementation version should be boring, reliable, contract-first, testable, and statistically conservative.

---

# 1. Skeptical Review of v0

## 1.1 Overly Broad Scope

v0 attempted to include:

* Ingestion
* Profiling
* Schema validation
* Joins
* Feature engineering
* OLS regression
* Logistic regression
* Predictive modeling
* Pattern scanning
* Multiple-testing correction
* Robustness checks
* Report generation
* HTML rendering
* Future extensibility for causal methods

That is directionally correct, but too much for the first working version.

The riskiest overreach is **pattern scanning**. Broad pattern detection creates a false-discovery problem immediately. It also requires careful multiple-testing families, effect-size thresholds, validation logic, and report wording. Implementing it too early could make the platform produce impressive but unreliable “findings.”

v1 moves broad pattern scanning out of the first implementation version.

---

## 1.2 Missing or Weak Module Boundaries

v0 had good module names, but some responsibilities were still too fuzzy.

Problem areas:

1. `patterns` and `validation` overlapped.
2. `features` and `modeling` overlapped around leakage and preprocessing.
3. `reporting` could accidentally become a second analytics pipeline.
4. `pipeline` risked becoming a god object.
5. `catalog` and `lineage` risked becoming coupled.

v1 clarifies that:

* `pipeline` orchestrates only.
* Domain modules do not call each other.
* Reporting never recomputes analytics.
* Modeling consumes only model-ready feature references.
* Join validation is not statistical validation.
* Leakage checks belong to feature preparation.
* Statistical validation validates model outputs and pre-specified tests in v1, not arbitrary pattern scans.

---

## 1.3 Ambiguous Input/Output Contracts

The biggest ambiguous contracts in v0 were:

### `DatasetHandle`

Ambiguity:

* Is it a Polars LazyFrame?
* A DuckDB relation?
* A file path?
* An in-memory object?
* A serialized artifact?

v1 decision:

`DatasetHandle` is a typed metadata reference only. It does not contain a dataframe. It points to a registered dataset through a backend-neutral reference.

---

### `FeatureMatrixResult`

Ambiguity:

* Does it contain the actual matrix?
* Does it contain paths?
* Does it contain train/test objects?

v1 decision:

`FeatureMatrixResult` contains metadata and `FeatureMatrixRef` objects. It does not contain large matrix objects.

---

### `ModelResult`

Ambiguity:

* Does it contain a raw Statsmodels result?
* A Scikit-learn estimator?
* A serialized object?
* Typed summary values?

v1 decision:

`ModelResult` contains typed summaries only. Raw model objects are private implementation details. Optional model artifacts may be referenced later through `ArtifactRef`.

---

### `ReportInputBundle`

Ambiguity:

* Does it accept anything?
* Does it require all pipeline stages?
* Does profile-only reporting work?

v1 decision:

`ReportInputBundle` is explicit and supports skipped stages through typed `StageResult` records.

---

## 1.4 Risk of Downstream Type Mismatch

v0 was vulnerable to this failure pattern:

1. `io` returns a Polars object.
2. `schema` expects a file path.
3. `profiling` expects a DuckDB relation.
4. `modeling` expects a Pandas DataFrame.
5. `reporting` expects serialized JSON.

v1 prevents this by requiring:

* Public result objects at every boundary.
* A private runtime dataset store behind `DatasetHandle`.
* Stage-specific request/result types.
* Contract compatibility tests between adjacent modules.

---

## 1.5 Circular Dependency Risks

The original map mostly avoided circular imports, but several areas were risky:

* `reporting` importing many domain result types.
* `validation` importing modeling implementation.
* `features` importing joins.
* `catalog` owning lineage while joins/features/modeling also need lineage.
* Domain modules importing `AnalysisPlan`.

v1 fixes this by:

* Moving lineage contracts to `contracts/lineage.py`.
* Keeping `AnalysisPlan` out of domain modules.
* Forcing domain modules to consume narrow request objects.
* Allowing `reporting` to import contracts only, never implementations.
* Making `pipeline` the only cross-domain orchestrator.

---

## 1.6 Where AI Coding Models Could Become Confused

AI coding tools are likely to make mistakes where architecture is implicit.

High-risk confusion points:

1. Implementing analytics before contracts.
2. Passing raw dictionaries between modules.
3. Letting `AnalysisPlan` leak into every module.
4. Returning raw Polars/Pandas/Statsmodels objects from public APIs.
5. Making reporting recompute statistics.
6. Weakening validation to pass tests.
7. Creating circular imports to “just make it work.”
8. Expanding MVP to advanced ML or automatic insights too soon.
9. Treating p-values as final conclusions.
10. Treating joins as simple dataframe operations instead of validation-sensitive operations.

v1 adds stricter AI coding rules and moves complex features later.

---

## 1.7 Statistical Error Risks

The major statistical risks are:

1. **False discoveries** from broad scans.
2. **Bad joins** producing inflated rows or duplicated outcomes.
3. **Target leakage** creating fake predictive performance.
4. **Train/test contamination** through preprocessing before splitting.
5. **Inappropriate regression** from wrong target type, bad sample size, high multicollinearity, or invalid assumptions.
6. **Causal overclaims** from observational associations.
7. **Overfitting** from too many predictors relative to rows.
8. **P-value worship** without effect sizes or confidence intervals.
9. **Ignoring missingness mechanisms**.
10. **Unstable results on small samples**.

v1 reduces these by:

* Removing broad pattern scanning from MVP.
* Making joins validation-gated.
* Making feature building leakage-gated.
* Making OLS the first modeling target.
* Requiring diagnostics and report limitations.
* Blocking causal language entirely in v1.
* Requiring synthetic known-answer tests.

---

## 1.8 Hidden Coupling Risks

v0 had hidden coupling risks around:

* Dataset storage representation.
* Report content depending on implementation details.
* Modeling depending on feature implementation internals.
* Validation depending on model library internals.
* Pipeline config leaking everywhere.

v1 introduces stable reference objects:

* `DatasetHandle`
* `DatasetRef`
* `FeatureMatrixRef`
* `ArtifactRef`
* `LineageRecord`
* `StageResult`

These are the stable cross-module objects. Heavy runtime objects stay private.

---

## 1.9 Missing Tests

v0 had good test categories, but v1 requires more compatibility tests before implementation.

Added emphasis:

* Stage adjacency contract tests.
* Contract serialization round trips.
* Skipped-stage behavior.
* Import boundary tests.
* Report wording tests.
* Synthetic statistical tests.
* Million-row performance smoke test, not full benchmark.

---

## 1.10 Performance Risks With Millions of Rows

Major risks:

1. Accidentally loading everything into Pandas.
2. Profiling every value exactly when approximate summaries are enough.
3. Join validation doing expensive full materialization.
4. Modeling trying to fit in-memory on millions of rows without limits.
5. Report generation embedding huge tables.
6. Pydantic contracts attempting to serialize dataframes or large column arrays.

v1 decisions:

* Use Polars lazy execution as the default local dataframe engine.
* Keep Pandas limited to modeling handoff when necessary.
* Do not store dataframes in contracts.
* Add explicit modeling row limits and sampling policy.
* Add profiling approximation settings.
* Add join validation thresholds.
* Add performance smoke test with a large synthetic dataset.
* Keep DuckDB as a future optional execution backend, not mandatory in v1.

---

## 1.11 What Should Move Out of the First Version

Moved out of first implementation version:

* Broad pattern scanning.
* Logistic regression, unless OLS is already stable.
* Scikit-learn pipelines beyond basic split utilities.
* Cross-validation.
* Complex robustness checks.
* Automatic insight generation.
* PDF export.
* Database connectors.
* JSONL ingestion.
* Interactive dashboards.
* Causal inference.
* Advanced ML model search.
* DuckDB execution backend abstraction.
* Persisted model artifacts.
* Pandera integration.

These remain valid future extensions.

---

# 2. Architecture Pack v1 — Product Scope

## 2.1 Product Goal

Build a Python analytics platform that can process tabular datasets through a reproducible, validated analytical workflow.

The long-term platform should support:

* Data ingestion
* Dataset profiling
* Safe joins
* Regression and multivariable modeling
* Pattern detection
* Statistical validation
* Reproducible reporting

The first implementation version should prove the foundation without trying to automate all insight discovery.

---

## 2.2 v1 MVP Scope

The v1 MVP includes:

1. Local CSV ingestion.
2. Local Parquet ingestion.
3. Dataset registration.
4. Dataset schema inference.
5. Optional expected schema validation.
6. Dataset profiling.
7. Safe join validation.
8. Safe join execution.
9. OLS regression only.
10. Basic feature matrix preparation for OLS.
11. Leakage checks for target and obvious post-outcome features.
12. Regression diagnostics.
13. Statistical validation of model outputs.
14. Markdown report generation.
15. HTML report generation if simple.
16. Run manifest.
17. CLI command to run an analysis from config.
18. Contract tests.
19. Integration smoke tests.

---

## 2.3 v1 MVP Non-Scope

Out of v1 MVP:

* Broad automatic pattern scanning.
* Logistic regression.
* Classification.
* Scikit-learn model training.
* Cross-validation.
* Hyperparameter tuning.
* Advanced feature engineering.
* Time-series modeling.
* Causal inference.
* Dashboard UI.
* PDF export.
* Database connectors.
* Cloud execution.
* Multi-user support.
* LLM-generated findings.
* Automatic data cleaning.
* Complex missingness imputation.
* Distributed execution.

---

## 2.4 v1 Success Criteria

v1 is successful when the platform can:

1. Load one or two local datasets.
2. Validate and profile them.
3. Block unsafe joins.
4. Execute safe joins.
5. Build an OLS feature matrix from explicit feature and target specs.
6. Block obvious leakage.
7. Fit an OLS model on safe data.
8. Produce diagnostics and limitations.
9. Produce a reproducible Markdown report.
10. Produce a run manifest.
11. Pass contract and integration tests.

---

# 3. Boring, Reliable Tech Stack

## 3.1 Required v1 Stack

* Python 3.12.13
* `uv`
* Pydantic
* Polars
* PyArrow
* Statsmodels
* NumPy
* SciPy
* Jinja2
* Typer
* Rich
* Pytest
* Ruff
* Mypy or Pyright

## 3.2 Deferred Stack

Deferred from v1:

* DuckDB
* Scikit-learn modeling
* Pandera
* PDF rendering
* Dashboard tools
* Cloud libraries

## 3.3 Rationale

Polars is sufficient for v1 ingestion, profiling, and joins. DuckDB is useful later, but adding two execution engines too early increases the chance of inconsistent behavior.

Statsmodels is appropriate for OLS and statistical summaries.

Pandas may be used only as a private modeling conversion layer because Statsmodels commonly expects Pandas-like inputs. Pandas objects must not cross public module boundaries.

---

# 4. Repository Structure v1

```text
analytics-platform/
  .python-version
  .gitignore
  README.md
  pyproject.toml
  uv.lock

  docs/
    architecture/
      architecture-pack-v1.md
      dependency-rules-v1.md
      statistical-validation-strategy-v1.md
      file-size-rules-v1.md

    contracts/
      interface-map-v1.md
      contracts-index-v1.md
      common-contracts.md
      dataset-contracts.md
      lineage-contracts.md
      schema-contracts.md
      profiling-contracts.md
      join-contracts.md
      feature-contracts.md
      modeling-contracts.md
      validation-contracts.md
      reporting-contracts.md
      pipeline-contracts.md

    prompts/
      llm-system-context.md
      module-build-template.md
      module-review-template.md
      contract-review-template.md

  src/
    analytics_platform/
      __init__.py

      contracts/
        __init__.py
        common.py
        datasets.py
        lineage.py
        schemas.py
        profiling.py
        joins.py
        features.py
        modeling.py
        validation.py
        reporting.py
        pipeline.py

      core/
        __init__.py
        config.py
        errors.py
        logging.py
        runtime.py
        artifact_paths.py

      io/
        __init__.py
        readers.py
        format_detection.py

      catalog/
        __init__.py
        dataset_registry.py
        runtime_store.py
        lineage_store.py

      schema/
        __init__.py
        inference.py
        validation.py

      profiling/
        __init__.py
        profiler.py
        summaries.py

      joins/
        __init__.py
        validator.py
        executor.py

      features/
        __init__.py
        builder.py
        leakage_checks.py

      modeling/
        __init__.py
        ols.py
        diagnostics.py

      validation/
        __init__.py
        model_validation.py
        claim_rules.py

      reporting/
        __init__.py
        report_builder.py
        markdown_renderer.py
        html_renderer.py

      pipeline/
        __init__.py
        orchestrator.py
        stage_runner.py
        run_manifest.py

      cli/
        __init__.py
        app.py

  tests/
    contracts/
    unit/
    integration/
    architecture/
    fixtures/
      datasets/
      configs/

  examples/
    configs/
      profile_only.yaml
      safe_join_ols.yaml
      unsafe_join_blocked.yaml
    data/
      README.md

  artifacts/
    .gitkeep
```

## 4.1 Removed From v1 Structure

Removed for now:

* `patterns/`
* `classification.py`
* `multiple_testing.py`
* `robustness.py`
* `scanner.py`
* Advanced report templates
* Database connector modules

These should be added only after v1 foundations are stable.

---

# 5. Major Modules, Inputs, Outputs, and Consumers

## 5.1 `contracts`

Purpose:

Own all public cross-module types.

Inputs:

* None.

Outputs:

* Pydantic models.
* Enums.
* Typed result objects.

Downstream consumers:

* All modules.

Rules:

* No implementation imports.
* No heavy compute dependencies.
* No dataframe objects in public fields.
* No raw library model objects in public fields.

---

## 5.2 `core`

Purpose:

Provide infrastructure.

Inputs:

* Config path.
* Runtime environment.

Outputs:

* `AnalysisPlan`
* runtime metadata
* artifact paths
* standardized errors
* logging setup

Downstream consumers:

* Pipeline
* CLI
* domain modules for shared utilities

Rules:

* May import contracts.
* Must not import domain implementation modules.
* Must not perform analytics.

---

## 5.3 `io`

Purpose:

Read local CSV and Parquet files into the private runtime dataset store.

Public input:

* `DatasetLoadRequest`

Public output:

* `DatasetLoadResult`

Downstream consumers:

* `catalog`
* `pipeline`

Rules:

* May use Polars and PyArrow.
* Must not expose Polars objects through public contracts.
* Must not infer analytical meaning.
* Must not validate schema beyond basic load/parsing status.

---

## 5.4 `catalog`

Purpose:

Register loaded and derived datasets.

Public input:

* `DatasetLoadResult`
* `JoinedDatasetResult`

Public output:

* `RegisteredDatasetResult`
* `DatasetHandle`
* `LineageRecord`

Downstream consumers:

* `schema`
* `profiling`
* `joins`
* `features`
* `pipeline`
* `reporting`

Rules:

* Owns private runtime store access.
* Maps `DatasetId` to private Polars lazy objects or materialized artifacts.
* Does not perform analytics.
* Does not validate joins.
* Does not fit models.

---

## 5.5 `schema`

Purpose:

Infer and validate dataset schemas.

Public input:

* `SchemaInferenceRequest`
* `SchemaValidationRequest`

Public output:

* `ObservedSchema`
* `SchemaValidationReport`

Downstream consumers:

* `profiling`
* `joins`
* `features`
* `reporting`
* `pipeline`

Rules:

* Does not profile distributions beyond schema needs.
* Does not call profiling.
* Does not modify datasets.
* Emits uncertainty where type inference is ambiguous.

---

## 5.6 `profiling`

Purpose:

Produce descriptive profiles.

Public input:

* `ProfilingRequest`

Public output:

* `DatasetProfile`

Downstream consumers:

* `joins`
* `features`
* `reporting`
* `pipeline`

Rules:

* Descriptive only.
* No validated findings.
* No causal language.
* No broad pattern scanning in v1.
* Must support approximate profiling settings for large datasets.

---

## 5.7 `joins`

Purpose:

Validate and execute joins.

Public inputs:

* `JoinValidationRequest`
* `JoinExecutionRequest`

Public outputs:

* `JoinValidationReport`
* `JoinedDatasetResult`

Downstream consumers:

* `catalog`
* `schema`
* `profiling`
* `features`
* `reporting`
* `pipeline`

Rules:

* Join validation must happen before join execution.
* Unsafe joins are blocked by default.
* Join execution consumes a passed `JoinValidationReport`.
* Joins do not perform modeling.
* Joins do not produce statistical findings.

---

## 5.8 `features`

Purpose:

Create model-ready feature matrix references and detect leakage.

Public inputs:

* `FeatureBuildRequest`
* `LeakageCheckRequest`

Public outputs:

* `FeatureMatrixResult`
* `LeakageCheckReport`

Downstream consumers:

* `modeling`
* `validation`
* `reporting`
* `pipeline`

Rules:

* Consumes explicit target and feature specs.
* Does not choose target automatically.
* Does not run models.
* Does not expose raw matrices in contracts.
* Must block obvious leakage by default.
* Must split before fitted preprocessing.

---

## 5.9 `modeling`

Purpose:

Fit OLS models and produce model diagnostics.

Public inputs:

* `ModelFitRequest`
* `ModelDiagnosticRequest`

Public outputs:

* `ModelResult`
* `ModelDiagnosticReport`

Downstream consumers:

* `validation`
* `reporting`
* `pipeline`

Rules:

* v1 supports OLS only.
* Consumes `FeatureMatrixResult`, not `DatasetHandle`.
* Does not perform feature building.
* Does not perform broad pattern scanning.
* Does not make causal claims.
* Does not expose Statsmodels objects publicly.

---

## 5.10 `validation`

Purpose:

Validate model results and enforce claim rules.

Public input:

* `ModelValidationRequest`

Public output:

* `ModelValidationReport`

Downstream consumers:

* `reporting`
* `pipeline`

Rules:

* v1 validates model results, not arbitrary pattern scans.
* Blocks causal language.
* Requires effect sizes, uncertainty, sample size, diagnostics, and limitations.
* Downgrades weak or assumption-violating model interpretations.
* Does not fit models.
* Does not recompute features.

---

## 5.11 `reporting`

Purpose:

Build and render reports from typed results.

Public inputs:

* `ReportBuildRequest`
* `ReportRenderRequest`

Public outputs:

* `ReportInputBundle`
* `ReportArtifactSet`

Downstream consumers:

* `pipeline`
* `cli`

Rules:

* Must not import domain implementations.
* Must not recompute analytics.
* Must not strengthen claim language.
* Must show warnings and limitations.
* Must support skipped sections.

---

## 5.12 `pipeline`

Purpose:

Orchestrate the full run.

Public input:

* `AnalysisPlan`

Public output:

* `AnalysisRunResult`

Downstream consumers:

* `cli`

Rules:

* Only pipeline orchestrates across modules.
* Stops or skips stages according to typed stage status.
* Converts `AnalysisPlan` into narrow module request objects.
* Collects stage outputs.
* Writes manifest.
* Returns typed result.

---

## 5.13 `cli`

Purpose:

Expose the pipeline through command line.

Public input:

* User command and config path.

Public output:

* Terminal status and artifact paths.

Rules:

* Thin wrapper.
* Does not call domain modules directly.
* Does not contain analytics logic.

---

# 6. Canonical Pipeline Flow v1

## 6.1 Profile-Only Flow

1. Load config into `AnalysisPlan`.
2. Load dataset with `DatasetLoadRequest`.
3. Register dataset.
4. Infer schema.
5. Validate schema if expected schema exists.
6. Profile dataset.
7. Build report input bundle.
8. Render Markdown report.
9. Render optional HTML report.
10. Write run manifest.
11. Return `AnalysisRunResult`.

---

## 6.2 Safe Join Flow

1. Complete profile-only prerequisites for each input dataset.
2. Build `JoinValidationRequest`.
3. Produce `JoinValidationReport`.
4. If join is approved, build `JoinExecutionRequest`.
5. Execute join.
6. Register joined dataset.
7. Infer joined schema.
8. Profile joined dataset.
9. Report join validation and joined profile.

---

## 6.3 OLS Modeling Flow

1. Complete dataset loading, schema, profiling, and optional join flow.
2. Build `FeatureBuildRequest`.
3. Produce `FeatureMatrixResult`.
4. Build `LeakageCheckRequest`.
5. Produce `LeakageCheckReport`.
6. If leakage is blocking, stop modeling.
7. Build `ModelFitRequest`.
8. Fit OLS.
9. Produce `ModelResult`.
10. Build `ModelDiagnosticRequest`.
11. Produce `ModelDiagnosticReport`.
12. Build `ModelValidationRequest`.
13. Produce `ModelValidationReport`.
14. Report model, diagnostics, validation, and limitations.

---

# 7. v1 Public Contracts by File

## 7.1 `contracts/common.py`

Owns:

* `RunId`
* `DatasetId`
* `ColumnName`
* `ModelId`
* `ReportId`
* `ArtifactId`
* `LineageId`
* `StageId`
* `Severity`
* `ExecutionStatus`
* `Issue`
* `WarningRecord`
* `MetricValue`
* `ArtifactRef`
* `StageResult`
* `ContentHash`
* `Timestamp`
* `RandomSeed`

Used by:

* All modules.

Must not import:

* Any other platform contract file except possibly standard typing helpers.
* Any implementation module.

---

## 7.2 `contracts/datasets.py`

Owns:

* `DatasetFormat`
* `DatasetRole`
* `StorageBackend`
* `DatasetMaterializationStatus`
* `DatasetLoadRequest`
* `DatasetLoadResult`
* `DatasetHandle`
* `DatasetRef`
* `IngestionReport`
* `RegisteredDatasetResult`
* `DatasetFingerprint`

Used by:

* `io`
* `catalog`
* `schema`
* `profiling`
* `joins`
* `features`
* `reporting`
* `pipeline`

Important decision:

`DatasetHandle` contains references and metadata only. It does not contain a dataframe.

---

## 7.3 `contracts/lineage.py`

Owns:

* `LineageOperationType`
* `LineageRecord`
* `LineageGraphSnapshot`
* `SourceDatasetRef`
* `DerivedDatasetRef`
* `TransformationRef`

Used by:

* `catalog`
* `joins`
* `features`
* `modeling`
* `reporting`
* `pipeline`

Important decision:

Lineage is not owned by catalog implementation. It is a shared contract.

---

## 7.4 `contracts/schemas.py`

Owns:

* `LogicalDataType`
* `PhysicalDataType`
* `ColumnSchema`
* `ObservedSchema`
* `ExpectedColumnSchema`
* `ExpectedSchema`
* `SchemaInferenceRequest`
* `SchemaValidationRequest`
* `SchemaValidationReport`
* `SchemaIssue`

Used by:

* `schema`
* `profiling`
* `joins`
* `features`
* `reporting`
* `pipeline`

---

## 7.5 `contracts/profiling.py`

Owns:

* `ProfilingSpec`
* `ProfilingRequest`
* `DatasetProfile`
* `ColumnProfile`
* `NumericProfile`
* `CategoricalProfile`
* `DatetimeProfile`
* `MissingnessProfile`
* `CardinalityProfile`
* `DuplicateProfile`
* `OutlierProfile`

Used by:

* `profiling`
* `joins`
* `features`
* `reporting`
* `pipeline`

Important decision:

No `CandidateFinding` in v1 profiling. Profiling emits warnings and summaries only.

---

## 7.6 `contracts/joins.py`

Owns:

* `JoinType`
* `JoinCardinality`
* `JoinRiskLevel`
* `JoinApprovalStatus`
* `ColumnConflictPolicy`
* `NullKeyPolicy`
* `DuplicateKeyPolicy`
* `JoinSpec`
* `JoinValidationRequest`
* `JoinValidationReport`
* `JoinExecutionRequest`
* `JoinExecutionReport`
* `JoinedDatasetResult`

Used by:

* `joins`
* `reporting`
* `pipeline`

Important decision:

Join validation is separate from statistical validation.

---

## 7.7 `contracts/features.py`

Owns:

* `TargetSpec`
* `FeatureSpec`
* `SplitSpec`
* `FeatureBuildRequest`
* `FeatureMatrixRef`
* `FeatureMatrixResult`
* `LeakageCheckRequest`
* `LeakageCheckReport`
* `LeakageRisk`
* `MissingValueStrategy`
* `EncodingStrategy`
* `ScalingStrategy`
* `SplitStrategy`

Used by:

* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

Important decision:

Feature matrices are referenced, not passed as dataframe objects.

---

## 7.8 `contracts/modeling.py`

Owns:

* `ModelType`
* `TargetType`
* `OLSModelSpec`
* `ModelSpec`
* `ModelFitRequest`
* `ModelResult`
* `ModelCoefficient`
* `CoefficientTable`
* `ModelMetricSet`
* `ModelDiagnosticRequest`
* `ModelDiagnosticReport`
* `RegressionDiagnosticSummary`
* `AssumptionCheckResult`
* `OverfittingCheckResult`
* `ModelInterpretationLimit`

Used by:

* `modeling`
* `validation`
* `reporting`
* `pipeline`

Important decision:

v1 `ModelType` supports OLS only.

---

## 7.9 `contracts/validation.py`

Owns:

* `ValidationSpec`
* `ModelValidationRequest`
* `ModelValidationReport`
* `ValidatedModelInterpretation`
* `RejectedModelInterpretation`
* `EvidenceGrade`
* `ClaimLevel`
* `CausalClaimPolicy`
* `ApprovedWording`
* `DisallowedWording`

Used by:

* `validation`
* `reporting`
* `pipeline`

Important decision:

v1 validation is model-focused. Broad finding validation comes later.

---

## 7.10 `contracts/reporting.py`

Owns:

* `ReportFormat`
* `ReportSpec`
* `ReportBuildRequest`
* `ReportInputBundle`
* `ReportSection`
* `ReportRenderRequest`
* `ReportArtifactSet`
* `ReportWarningSummary`
* `ReportClaimSummary`

Used by:

* `reporting`
* `pipeline`
* `cli`

Important decision:

Reporting consumes typed results and skipped-stage records.

---

## 7.11 `contracts/pipeline.py`

Owns:

* `AnalysisPlan`
* `AnalysisRunResult`
* `PipelineStageName`
* `PipelineExecutionMode`
* `PipelineFailurePolicy`
* `RunManifestRequest`
* `RunManifest`
* `PipelineWarningSummary`

Used by:

* `core.config`
* `pipeline`
* `cli`

Important decision:

Domain modules must not import `contracts.pipeline`.

---

# 8. Dependency Rules v1

## 8.1 Layering

Allowed dependency direction:

```text
contracts
  <- core
  <- domain modules
  <- pipeline
  <- cli
```

In import terms:

* `core` may import `contracts`.
* Domain modules may import `contracts` and `core`.
* `pipeline` may import domain modules, `core`, and `contracts`.
* `cli` may import `pipeline`, `core`, and selected contracts.

Lower-level modules must not import higher-level modules.

---

## 8.2 Domain Module Rule

Domain modules must not orchestrate each other.

Incorrect:

* `profiling` calls `schema.inference`.
* `modeling` calls `features.builder`.
* `reporting` calls `modeling.ols`.

Correct:

* `pipeline` calls `schema`.
* `pipeline` passes `ObservedSchema` to `profiling`.
* `pipeline` passes `FeatureMatrixResult` to `modeling`.
* `pipeline` passes `ModelResult` to `reporting`.

---

## 8.3 Forbidden Imports

Forbidden:

* `contracts` importing implementation modules.
* `core` importing domain modules.
* Domain modules importing `pipeline`.
* Domain modules importing `cli`.
* `reporting` importing domain implementation modules.
* `modeling` importing `validation`.
* `features` importing `modeling`.
* `joins` importing `features` or `modeling`.
* `schema` importing `profiling`.
* `profiling` importing `joins`, `features`, or `modeling`.

---

## 8.4 Reporting Special Rule

Reporting may import domain result contracts.

Reporting may not import domain implementation modules.

Allowed:

* `contracts.modeling.ModelResult`
* `contracts.validation.ModelValidationReport`

Forbidden:

* `modeling.ols`
* `validation.model_validation`
* `profiling.profiler`
* `joins.executor`

---

## 8.5 Pipeline Special Rule

Pipeline is allowed to import all domain implementations.

But pipeline must remain thin by using stage runners.

Recommended split:

* `pipeline/orchestrator.py` handles high-level run.
* `pipeline/stage_runner.py` converts plan sections into stage requests.
* `pipeline/run_manifest.py` writes manifest.

No single pipeline file should become a 700-line orchestrator.

---

# 9. v1 Statistical Validation Strategy

## 9.1 v1 Statistical Claim Levels

Allowed claim levels in v1:

1. `DESCRIPTIVE`
2. `ASSOCIATIONAL`
3. `PREDICTIVE_LIMITED`
4. `UNSUPPORTED`
5. `BLOCKED`

Not allowed in v1:

* `CAUSAL`

---

## 9.2 OLS Interpretation Rules

OLS output may be interpreted only as associational unless a future causal module exists.

Reports may say:

* “In this dataset, X is associated with Y after adjusting for listed covariates.”
* “The estimated coefficient for X is positive/negative under this model specification.”
* “This relationship is not causal evidence.”

Reports may not say:

* “X causes Y.”
* “Changing X will change Y.”
* “The model proves that X drives Y.”
* “The platform discovered the reason for Y.”

---

## 9.3 Minimum OLS Diagnostics

v1 OLS diagnostics must include:

* Number of rows used.
* Number of features.
* Missing rows dropped or handled.
* Coefficients.
* Standard errors.
* Confidence intervals.
* P-values, if available.
* R-squared and adjusted R-squared.
* Residual warning summary.
* Multicollinearity warning, at minimum using a simple threshold or VIF later.
* Train/test metric gap if train/test split is configured.
* Sample-size-to-feature warning.
* High-cardinality feature warning.
* Constant or near-constant feature warning.
* Leakage warning summary.

---

## 9.4 P-Value Rules

P-values are never enough.

Every reported model interpretation must include:

* Coefficient or effect estimate.
* Direction.
* Confidence interval where available.
* Sample size.
* Model specification.
* Limitations.
* Claim level.

If the result is statistically significant but tiny, the report must say practical significance may be limited.

---

## 9.5 Missingness Rules

The platform must report:

* Rows before modeling.
* Rows after dropping missing values.
* Drop rate.
* Columns responsible for missingness.
* Whether missingness handling may bias results.

v1 should use simple, explicit missingness strategies only:

* Error on missingness.
* Drop rows with missing model fields.
* Fill numeric with constant only if explicitly configured.
* Fill categorical with explicit “missing” category only if configured.

No automatic sophisticated imputation in v1.

---

## 9.6 Leakage Rules

Blocking leakage risks in v1:

* Target column included as feature.
* Feature column has same values as target.
* Feature name is target plus suffix/prefix indicating direct leakage.
* Explicit post-outcome column is included when time metadata exists.
* Train/test split contamination is detected.

Warnings but not always blocking:

* ID-like columns used as predictors.
* High-cardinality categorical columns.
* Feature names semantically similar to target.
* Date columns after target event when metadata is incomplete.

---

## 9.7 Join Statistical Safety

A model based on a joined dataset must include join validation status.

If the join had warnings, model interpretation must be downgraded or caveated.

If the join was blocked, modeling cannot proceed unless explicit override exists.

Overrides must be recorded in the manifest and report.

---

# 10. Performance Architecture v1

## 10.1 Dataset Size Assumptions

v1 should support datasets with millions of rows for:

* Loading
* Schema inference
* Profiling
* Join validation
* Joins where feasible

v1 does not promise to fit OLS on unlimited rows and columns.

---

## 10.2 Dataframe Rules

* Polars lazy execution is the default internal dataframe approach.
* Public contracts never contain dataframes.
* Pandas conversion is allowed only inside modeling.
* Pandas conversion must be explicit, bounded, and reported.
* Modeling should fail with a clear error if the feature matrix exceeds configured limits.

---

## 10.3 Profiling Performance Rules

Profiling must support:

* Exact mode for small datasets.
* Approximate/sample mode for large datasets.
* Configurable row sample limit.
* Configurable expensive-statistics flag.
* No full value list serialization.

Column profiles should report summary values, not entire distributions.

---

## 10.4 Join Performance Rules

Join validation should avoid full materialization where possible.

It must report:

* Left row count.
* Right row count.
* Null key counts.
* Duplicate key indicators.
* Estimated cardinality.
* Estimated row explosion risk.

For very large joins, exact duplicate counts may be expensive. v1 may use exact counts initially, but the contract should allow approximate flags.

---

## 10.5 Reporting Performance Rules

Reports must not embed:

* Full datasets.
* Huge tables.
* Thousands of coefficients.
* Full residual arrays.
* Full distributions.

Reports should include:

* Top warnings.
* Summary tables.
* Artifact references.

---

# 11. v1 Contract Tests

Contract tests must be written before domain implementation.

## 11.1 Required Contract Tests

### Config to Pipeline

Proves:

* YAML/TOML config can become `AnalysisPlan`.
* Invalid configs fail.
* Domain modules do not consume raw config dictionaries.

### IO to Catalog

Proves:

* `DatasetLoadResult` can become `RegisteredDatasetResult`.
* Dataset ID consistency is preserved.
* Ingestion report references the dataset handle.

### Catalog to Schema

Proves:

* `SchemaInferenceRequest` can consume `DatasetHandle`.
* No raw dataframe is required by the public contract.

### Schema to Profiling

Proves:

* `ProfilingRequest` can consume `DatasetHandle` and optional `ObservedSchema`.
* `DatasetProfile` references the same dataset.

### Schema/Profile to Join Validation

Proves:

* `JoinValidationRequest` can consume dataset handles, schemas, profiles, and `JoinSpec`.
* Join keys are representable as `ColumnName`.
* Join validation output has explicit approval status.

### Join Validation to Join Execution

Proves:

* `JoinExecutionRequest` requires passed validation.
* Blocked validation cannot be executed without explicit override.
* `JoinedDatasetResult` includes dataset handle and lineage.

### Dataset to Feature Build

Proves:

* `FeatureBuildRequest` can consume raw or joined dataset handle.
* Target and features are explicit.
* `FeatureMatrixResult` has `FeatureMatrixRef`.

### Feature Build to Leakage

Proves:

* `LeakageCheckRequest` consumes `FeatureMatrixResult`.
* Blocking risks are representable.
* Leakage report references target and feature matrix.

### Feature/Leakage to Modeling

Proves:

* `ModelFitRequest` consumes `FeatureMatrixResult` and `LeakageCheckReport`.
* Blocking leakage prevents model request validity unless override exists.
* `ModelResult` contains typed summary only.

### Modeling to Diagnostics

Proves:

* `ModelDiagnosticRequest` consumes `ModelResult`.
* Diagnostic report references same model ID.
* Diagnostics are typed.

### Modeling/Diagnostics/Leakage to Validation

Proves:

* `ModelValidationRequest` consumes `ModelResult`, `ModelDiagnosticReport`, and `LeakageCheckReport`.
* Validation output assigns claim level.
* Causal claim level is rejected in v1.

### All Results to Reporting

Proves:

* `ReportBuildRequest` can consume profile-only results.
* `ReportBuildRequest` can consume join-and-model results.
* Missing optional stages are represented as skipped.
* Reporting does not require raw dataframes or implementation objects.

### Reporting to Pipeline

Proves:

* `ReportArtifactSet` can be included in `AnalysisRunResult`.

### Pipeline to CLI

Proves:

* CLI can display status, warnings, and artifact paths from `AnalysisRunResult`.

---

# 12. v1 Integration Tests

## 12.1 Profile-Only Smoke Test

Input:

* One clean CSV.

Pipeline:

* Config
* Load
* Register
* Schema inference
* Schema validation
* Profiling
* Markdown report
* Manifest

Assertions:

* Run succeeds.
* Report exists.
* Manifest exists.
* Dataset profile exists.
* No model section appears.
* No causal language appears.

---

## 12.2 Dirty Dataset Profiling Test

Input:

* CSV with nulls, duplicate rows, mixed types, and high-cardinality column.

Assertions:

* Run succeeds with warnings or validation issues.
* Report includes data quality warnings.
* No unsupported claims appear.

---

## 12.3 Safe Join Test

Input:

* Left and right CSV with one-to-one keys.

Assertions:

* Join validation passes.
* Join executes.
* Joined dataset is registered.
* Join report includes pre/post row counts.
* Manifest includes lineage.

---

## 12.4 Unsafe Join Blocked Test

Input:

* Left and right CSV with many-to-many keys.

Assertions:

* Join validation blocks execution.
* Joined dataset is not created.
* Run result records blocked stage.
* Report or run summary explains the block.

---

## 12.5 OLS Known-Signal Test

Input:

* Synthetic dataset with known linear relationship.

Assertions:

* Feature matrix builds.
* Leakage check passes.
* OLS fits.
* Coefficient direction is correct.
* Model report says associational, not causal.

---

## 12.6 OLS No-Signal Test

Input:

* Synthetic dataset with no true relationship.

Assertions:

* Model fits.
* Validation does not produce strong claim.
* Report does not overstate noise.

---

## 12.7 Leakage Blocked Test

Input:

* Dataset with target duplicated as feature.

Assertions:

* Leakage check blocks modeling.
* Model is not fit.
* Report explains why.

---

## 12.8 Large Dataset Performance Smoke Test

Input:

* Synthetic CSV or Parquet with at least one million rows and modest number of columns.

Pipeline:

* Load
* Schema inference
* Profiling in approximate mode
* Report

Assertions:

* Does not convert entire dataset to Pandas.
* Does not embed large data in contracts.
* Completes without memory explosion under reasonable local constraints.
* Report marks profiling as approximate if sampling was used.

This is not a benchmark. It is a guard against obviously unsafe design.

---

# 13. File Size and Modularity Rules v1

## 13.1 File Limits

* Target file size: 150–300 lines.
* Soft max: 350 lines.
* Hard max: 400 lines unless explicitly justified.

## 13.2 Split Rules

Split files by responsibility before they exceed limits.

Examples:

* `modeling/ols.py` fits models.
* `modeling/diagnostics.py` diagnoses model outputs.
* `joins/validator.py` validates joins.
* `joins/executor.py` executes joins.
* `reporting/report_builder.py` assembles report data.
* `reporting/markdown_renderer.py` renders Markdown.

## 13.3 Function Rules

* Public functions should usually accept one request object and return one result object.
* Avoid long argument lists.
* Avoid raw dictionaries.
* Avoid hidden global state.
* Avoid side effects outside artifact writing and runtime store management.

---

# 14. LLM Prompting Rules v1

Every implementation prompt should include:

1. The exact module being implemented.
2. The owning contract file.
3. Allowed imports.
4. Forbidden imports.
5. Target tests.
6. File-size limits.
7. Instruction not to implement future phases.
8. Instruction not to change contracts unless asked.
9. Instruction not to pass raw dictionaries across module boundaries.
10. Instruction not to expose raw Polars/Pandas/Statsmodels objects publicly.
11. Instruction not to weaken validation to pass tests.
12. Instruction not to add causal language.

## 14.1 Standard Implementation Prompt Shape

Use this structure:

```text
Implement only [module/file].

Use these contracts:
- [contract files]

Allowed imports:
- [allowed imports]

Forbidden:
- [forbidden imports]

Tests to satisfy:
- [test files]

Do not:
- change public contracts
- implement future modules
- exceed file-size limits
- pass raw dictionaries across module boundaries
- expose raw dataframe/model objects in public contracts
- weaken validation rules
```

---

# 15. Development Phases v1

## Phase 0: Save Architecture v1

Tasks:

1. Save Architecture Pack v1.
2. Save Interface Map v1.
3. Save dependency rules.
4. Save statistical validation strategy.
5. Save prompt templates.

No Python implementation yet.

Exit criteria:

* Docs are committed.

---

## Phase 1: Project Scaffolding

Tasks:

1. Create `pyproject.toml`.
2. Configure dependencies.
3. Add package skeleton.
4. Configure pytest.
5. Configure Ruff.
6. Configure type checker.
7. Add import smoke test.

Exit criteria:

* Package imports.
* Tests run.
* No analytics logic.

---

## Phase 2: Contracts Only

Tasks:

1. Implement `contracts/common.py`.
2. Implement `contracts/datasets.py`.
3. Implement `contracts/lineage.py`.
4. Implement `contracts/schemas.py`.
5. Implement `contracts/profiling.py`.
6. Implement `contracts/joins.py`.
7. Implement `contracts/features.py`.
8. Implement `contracts/modeling.py`.
9. Implement `contracts/validation.py`.
10. Implement `contracts/reporting.py`.
11. Implement `contracts/pipeline.py`.
12. Add contract tests.

Exit criteria:

* All contract tests pass.
* Serialization round trips pass.
* Invalid objects fail validation.
* No implementation modules exist beyond skeletons.

---

## Phase 3: Core Infrastructure

Tasks:

1. Config loading.
2. Runtime metadata.
3. Artifact paths.
4. Error types.
5. Logging.
6. Run IDs.

Exit criteria:

* Config becomes `AnalysisPlan`.
* Runtime metadata exists.
* No domain analytics yet.

---

## Phase 4: IO and Catalog

Tasks:

1. CSV loading.
2. Parquet loading.
3. Dataset handle creation.
4. Runtime dataset store.
5. Dataset registration.
6. Ingestion reports.
7. Basic lineage.

Exit criteria:

* Datasets load.
* Handles are stable.
* Dataframes stay private.
* Contract tests pass.

---

## Phase 5: Schema

Tasks:

1. Schema inference.
2. Expected schema validation.
3. Schema issue reporting.

Exit criteria:

* Clean schema passes.
* Dirty schema produces issues.
* Schema outputs feed profiling.

---

## Phase 6: Profiling

Tasks:

1. Dataset profile.
2. Column profiles.
3. Missingness.
4. Cardinality.
5. Duplicates.
6. Numeric/categorical/datetime summaries.
7. Approximate mode.

Exit criteria:

* Profile-only smoke test can run through profiling.
* No claims or pattern findings are generated.

---

## Phase 7: Reporting for Profile-Only Runs

Tasks:

1. Report input bundle.
2. Markdown renderer.
3. Basic HTML renderer, optional.
4. Manifest integration.

Exit criteria:

* Profile-only smoke test passes.
* Report includes reproducibility metadata.
* Report includes warnings.
* No model sections appear when skipped.

---

## Phase 8: Joins

Tasks:

1. Join validation.
2. Join execution.
3. Joined dataset registration.
4. Join lineage.
5. Join reporting.

Exit criteria:

* Safe join test passes.
* Unsafe join blocked test passes.

---

## Phase 9: Features and Leakage

Tasks:

1. Feature build request handling.
2. Explicit target handling.
3. Explicit feature selection.
4. Basic missingness policy.
5. Train/test split support.
6. Leakage checks.
7. Feature matrix references.

Exit criteria:

* Leakage blocked test passes.
* Modeling receives `FeatureMatrixResult`.

---

## Phase 10: OLS Modeling

Tasks:

1. OLS fit.
2. Model result.
3. Regression diagnostics.
4. Typed coefficient table.
5. Basic metrics.

Exit criteria:

* Known-signal OLS test passes.
* No-signal OLS test passes.
* No raw Statsmodels object appears in public output.

---

## Phase 11: Model Validation and Claim Rules

Tasks:

1. Model validation report.
2. Claim-level assignment.
3. Causal language blocking.
4. Evidence grading.
5. Report wording restrictions.

Exit criteria:

* Reports use associational language.
* Weak/no-signal models do not become strong claims.
* Causal claims are impossible in v1 output.

---

## Phase 12: Full Pipeline and CLI

Tasks:

1. End-to-end orchestrator.
2. Stage runner.
3. Run manifest.
4. CLI `run`.
5. CLI `validate-config`.

Exit criteria:

* Profile-only pipeline works.
* Safe join OLS pipeline works.
* Unsafe join blocks.
* Leakage blocks.
* CLI displays artifact paths.

---

## Phase 13: Hardening

Tasks:

1. Architecture import tests.
2. Large dataset performance smoke test.
3. Documentation updates.
4. Example configs.
5. Prompt templates.
6. CI setup.

Exit criteria:

* Architecture boundaries are enforced.
* Large profiling does not obviously break memory.
* Future implementation prompts can rely on stable docs.

---

# 16. Risks and v1 Mitigations

## 16.1 Bad joins

Mitigation:

* Join validation before execution.
* Block many-to-many joins by default unless explicitly allowed.
* Report row multiplication.
* Preserve join lineage.

---

## 16.2 Leakage

Mitigation:

* Modeling cannot consume raw datasets.
* Modeling consumes only `FeatureMatrixResult`.
* Leakage report is required before model fit.
* Blocking leakage prevents modeling.

---

## 16.3 False discoveries

Mitigation:

* Broad pattern scanning moved out of v1.
* OLS results must pass validation and claim rules.
* No automatic insight generation.

---

## 16.4 Causal overclaiming

Mitigation:

* Causal claims are not supported in v1.
* Reporting uses approved wording.
* Validation blocks causal claim levels.

---

## 16.5 Type mismatches

Mitigation:

* One request and one result type per stage.
* Contract tests between adjacent stages.
* No raw dictionaries across module boundaries.
* No raw dataframe/model objects in contracts.

---

## 16.6 Circular imports

Mitigation:

* Domain modules do not import each other for orchestration.
* Pipeline is the only orchestrator.
* Domain modules do not import `contracts.pipeline`.
* Lineage is a shared contract, not catalog implementation.

---

## 16.7 LLM confusion

Mitigation:

* Smaller MVP.
* Explicit allowed imports.
* Explicit forbidden imports.
* Stable contract docs.
* Module-specific implementation prompts.
* File-size rules.

---

## 16.8 Performance collapse

Mitigation:

* Polars lazy execution.
* No Pandas except bounded modeling conversion.
* No dataframes in contracts.
* Approximate profiling mode.
* Large dataset smoke test.

---

# 17. Final v1 Architecture Decision

Architecture Pack v1 narrows the first version to a reliable foundation:

1. Load local tabular data.
2. Register datasets.
3. Infer and validate schemas.
4. Profile datasets.
5. Validate and execute safe joins.
6. Prepare explicit OLS feature matrices.
7. Block leakage.
8. Fit OLS.
9. Validate model interpretation.
10. Produce reproducible reports.

The most important changes from v0 are:

* Broad pattern scanning is moved out of v1.
* Logistic regression and classification are moved out of v1.
* DuckDB is deferred.
* Contracts are tightened around references, not raw data objects.
* Every stage has explicit request and result types.
* Reporting cannot recompute analytics.
* Modeling cannot consume raw datasets.
* Domain modules cannot orchestrate each other.
* Causal claims are impossible in v1.

This creates a smaller, safer, more implementable platform foundation while preserving the long-term project goal.
