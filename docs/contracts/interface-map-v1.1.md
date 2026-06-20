# Interface Map v1.1 — Stage Input/Output Map

Status: Active for Build Queue v2.1 Task 6.
Owner: Analytics Platform Team.
Scope: documentation-level stage-by-stage request/result flow for the
analytics-platform. This document defines the typed shape of data that crosses
module boundaries; it does not freeze Pydantic field definitions and does not
introduce implementation code.

Companion docs (do not duplicate, refer to them):
- `docs/architecture/architecture-pack-v1.1.md` — module inventory and canonical
  pipeline flow.
- `docs/architecture/quantitative-analysis-design-v1.1.md` — quantitative
  contracts added in v1.1.
- `docs/architecture/dependency-rules-v1.1.md` — import layering and forbidden
  imports.
- `docs/architecture/statistical-validation-strategy-v1.1.md` — claim levels,
  blocking, and downgrade behavior.
- `docs/contracts/contracts-index-v1.1.md` — contract family index.

## 1. Purpose

This document is the documentation-level source of truth for how typed objects
flow between pipeline stages and domain modules. It maps each canonical stage to:

1. Public inputs (request contracts).
2. Public outputs (result contracts).
3. Upstream dependencies (earlier stages or external inputs).
4. Downstream consumers (later stages or external consumers).
5. Blocking and skipped behavior (when a stage blocks, downgrades, or is
   skipped and represented as a typed `StageResult`).

It reinforces the contract-first rules:

- Every stage uses a typed `StageRequest -> StageResult` shape.
- Raw dictionaries are never passed across module boundaries.
- Raw Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, and Matplotlib objects
  never appear in public outputs.
- Public outputs use refs, handles, artifact refs, and typed summaries.
- Pipeline is the only cross-module orchestrator; domain modules do not call
  each other.
- Reporting consumes contracts/results only and never recomputes analytics.

Implementation of the referenced contracts is deferred to later Build Queue v2.1
contract tasks. This document defines documentation-level responsibilities and
compatibility expectations only.

## 2. Cross-stage shared object rules

The following shared objects are the stable cross-module carriers. Heavy runtime
objects stay private behind them.

- `DatasetHandle` — metadata reference to a registered dataset; never a dataframe.
- `DatasetRef` — stable dataset identity.
- `DatasetArtifactRef` — persisted dataset artifact reference.
- `LazyFrameRef` / `BackendObjectRef` — backend-neutral execution references;
  never expose raw library objects publicly.
- `FeatureMatrixRef` — model-ready matrix reference, not a raw matrix.
- `ArtifactRef` / `PersistedArtifact` — durable artifact references.
- `LineageRecord` — transformation lineage.
- `StageResult` — typed stage outcome with status and skipped/block reasons.

Any stage that needs to pass large data must pass a reference, not the object.

## 3. Canonical stage list

The v1.1 pipeline stages, in dependency order, are:

1. Config loading.
2. Dataset loading and ingestion.
3. Dataset registration.
4. Schema inference.
5. Semantic role inference.
6. Schema validation.
7. Data quality and missingness.
8. Distribution profiling.
9. Diagnostic association checks.
10. Join validation (optional).
11. Join execution (optional, gated by validation).
12. Joined dataset re-schema/re-profile/re-quality (optional).
13. Feature spec resolution.
14. Feature split planning.
15. Feature transformation planning.
16. Feature matrix build.
17. Leakage checks.
18. Model spec validation.
19. Modeling data adapter (bounded, private conversion).
20. OLS fit.
21. OLS result extraction.
22. Model fit metrics.
23. Model diagnostics.
24. Multiple-testing correction (optional within coefficient family).
25. Claim rules and causal blocking.
26. Robustness status (minimal, may be skipped).
27. Model validation.
28. Report bundle assembly.
29. Report rendering (Markdown, optional HTML).
30. Visual artifact generation (optional, deferred after profile-only MVP).
31. Run manifest writing.
32. File-based registry writing.
33. CLI result display.

Optional stages may be skipped and represented as typed skipped `StageResult`
records. Skipped stages must never be silently omitted.

## 4. Stage input/output map

Each row uses documentation-level request/result names. Exact field definitions
are owned by later contract tasks and are not frozen here. "Block" means the
stage produces a typed block reason and prevents downstream execution unless
explicitly overridden and recorded in lineage.

| Stage | Public input | Public output | Upstream | Downstream | Blocking/skipped |
| --- | --- | --- | --- | --- | --- |
| 4.1 Config loading | config path, runtime env | `AnalysisPlan` | external config | pipeline, CLI | invalid config blocks before any stage executes |
| 4.2 Dataset loading and ingestion | `DatasetLoadRequest` | `DatasetLoadResult`, `IngestionReport` | config, local CSV/Parquet | catalog, pipeline | missing file/unsupported format blocks; no raw dataframe in result |
| 4.3 Dataset registration | `DatasetLoadResult`, later `JoinedDatasetResult` | `RegisteredDatasetResult`, `DatasetHandle`, `LineageRecord` | IO | schema, semantics, quality, profiling, joins, features, reporting | duplicate/invalid identity blocks registration |
| 4.4 Schema inference | `SchemaInferenceRequest` | `ObservedSchema` | catalog | semantics, quality, profiling, joins, features, reporting | no raw dataframe required by public contract |
| 4.5 Semantic role inference | schema, optional user roles | `SemanticTypeInferenceReport` | schema | quality, joins, features, modeling, reporting | risky roles warn; explicit override may downgrade block to warning, recorded in lineage |
| 4.6 Schema validation | `SchemaValidationRequest` | `SchemaValidationReport` | schema inference | profiling, joins, features, reporting | mismatches produce typed issues; hard mismatches may block per failure policy |
| 4.7 Data quality and missingness | dataset handle, schema, semantic report | `DataQualityReport`, `MissingDataReport` | schema, semantics | profiling, joins, features, modeling, reporting | severe target-associated missingness may downgrade later associational outputs to unsupported |
| 4.8 Distribution profiling | `ProfilingRequest`, `ExecutionLimitPolicy` | `DatasetProfile`, `ColumnProfile`, distribution summaries | schema, quality | associations, joins, reporting | large datasets use approximate mode; profile states exact vs approximate; no claims produced |
| 4.9 Diagnostic association checks | `AssociationCheckRequest` | `AssociationCheckReport`, `PairwiseAssociationSummary`, multicollinearity risk summary | profiling, semantics | modeling diagnostics, reporting | diagnostic-only, never a finding; perfect associations trigger leakage re-checks, not conclusions |
| 4.10 Join validation (optional) | `JoinValidationRequest`, `JoinSpec` | `JoinValidationReport` (approval, semantic key compatibility, join-induced missingness, modeling risk level) | catalog, schema, semantics, quality, profiling | join execution, features, reporting | unsafe joins blocked by default; blocked joins cannot execute without override |
| 4.11 Join execution (optional, gated) | `JoinExecutionRequest` (approved validation) | `JoinedDatasetResult`, `JoinExecutionReport`, `LineageRecord` | join validation | catalog, schema, profiling, features, reporting | blocked validation cannot execute without override |
| 4.12 Joined dataset re-schema/re-profile/re-quality (optional) | `JoinedDatasetResult` | refreshed `ObservedSchema`, `DatasetProfile`, `DataQualityReport` | join execution | features, modeling, reporting | skipped if no join configured |
| 4.13 Feature spec resolution | `TargetSpec`, `FeatureSpec`, exclusions, dataset handle | `FeatureEligibilityReport` | catalog, schema, semantics | split planner, transformation planner, leakage checks | missing target/invalid feature refs block feature build |
| 4.14 Feature split planning | `SplitSpec`, `FeatureBuildRequest` | split refs, `requires_holdout` flag | feature spec resolution | transformation planner, modeling | predictive purpose requires holdout unless overridden; time split requires explicit time column |
| 4.15 Feature transformation planning | feature spec, split, semantic roles | `FeatureTransformationPlan`, `PreprocessingFitScope` | split planner | matrix builder, leakage checks | fitted transforms must declare train-only fit scope; otherwise block |
| 4.16 Feature matrix build | `FeatureBuildRequest` | `FeatureMatrixResult`, `FeatureMatrixRef`, `RowsExcludedReport`, `ColumnsExcludedReport` | transformation planner | leakage checks, modeling | no raw matrix object in public result |
| 4.17 Leakage checks | `LeakageCheckRequest` | `LeakageCheckReport`, `LeakageRisk` | feature matrix build | modeling, validation, reporting | target-as-feature, post-outcome predictors, train/test contamination blocking by default; warnings downgrade later outputs |
| 4.18 Model spec validation | `OLSModelSpec`, `ModelSpec` | `ModelSpecValidationReport` | feature spec, leakage checks | modeling data adapter, OLS fit | unsupported family, missing/constant target, no predictors, sample below minimum, predictive without holdout block; every block produces typed reason |
| 4.19 Modeling data adapter (private conversion) | `ModelFitRequest`, `ExecutionLimitPolicy` | bounded private conversion refs only; no public Pandas/Statsmodels object | feature matrix, execution limits | OLS fit | exceeding row/column limits blocks conversion with clear issue |
| 4.20 OLS fit | `ModelFitRequest` | `ModelResult` (typed summary only) | data adapter, model spec validation | result extraction, diagnostics, validation, reporting | no raw Statsmodels object in public output |
| 4.21 OLS result extraction | `ModelResult` | `CoefficientTable`, `ModelCoefficient`, `EffectEstimate`, `ConfidenceInterval` | OLS fit | metrics, diagnostics, validation, reporting | invalid p-values/missing intervals represented as typed issues |
| 4.22 Model fit metrics | `ModelResult` | `ModelMetricSet`, `MetricValue` | result extraction | diagnostics, validation, reporting | predictive-limited outputs must disclose holdout configuration |
| 4.23 Model diagnostics | `ModelDiagnosticRequest` | `ModelDiagnosticReport` (fit, assumption, data, stability, interpretation-limit sections) | result extraction, association diagnostics | validation, reporting | severe assumption violations downgrade coefficient-level interpretation |
| 4.24 Multiple-testing correction (optional) | `TestFamily`, p-values within declared family | `MultipleTestingCorrectionReport`, `PValueAdjustmentResult` | result extraction | validation, reporting | unadjusted p-values not discovery guarantees; skipped correction must be disclosed |
| 4.25 Claim rules and causal blocking | `ModelResult`, `ModelDiagnosticReport`, `LeakageCheckReport` | `ClaimLevel`, `EvidenceGrade`, `CausalWarning`, `ApprovedWording`, `DisallowedWording` | diagnostics, leakage, multiple-testing | validation, reporting | causal claim level blocked in MVP; weak evidence downgraded, not silently emitted |
| 4.26 Robustness status (minimal, may be skipped) | model and diagnostic refs | `RobustnessCheckResult`, `SkippedRobustnessCheck` | diagnostics | validation, reporting | skipped checks emitted as typed skipped records, not omitted |
| 4.27 Model validation | `ModelValidationRequest` | `ModelValidationReport`, `ValidatedModelInterpretation`, `RejectedModelInterpretation` | modeling, diagnostics, leakage, claim rules, robustness | reporting, pipeline | causal claims rejected; unsupported outputs downgraded and visible; blocks produce typed reasons |
| 4.28 Report bundle assembly | `ReportBuildRequest` | `ReportInputBundle`, `ReportSection` | all prior typed results | renderers, pipeline | missing optional stages represented as skipped sections; reporting never recomputes analytics |
| 4.29 Report rendering | `ReportRenderRequest` | `ReportArtifactSet` | report bundle | pipeline, CLI | reports must include causal disclaimer, claim level, limitations, skipped-check disclosure, missingness impact, join validation status, leakage status, diagnostic status |
| 4.30 Visual artifact generation (optional, deferred) | `VisualArtifactSpec` | `TableArtifactRef`, `ChartArtifactRef` | report bundle | renderers, registry | deferred after profile-only MVP; no large inline payloads |
| 4.31 Run manifest writing | `RunManifestRequest` | `RunManifest` | all stages, cache decisions | registry, reporting | manifest references config hash, dataset fingerprints, artifacts, stage statuses |
| 4.32 File-based registry writing | `RegistryWriteRequest` | `RegistryWriteResult`, `RunRegistryRecord` | manifest, artifacts | history, CLI | pipeline owns registry writing; domain modules do not write directly |
| 4.33 CLI result display | `AnalysisRunResult` | terminal status and artifact paths | pipeline | user | CLI is thin wrapper; does not call domain modules directly |

## 5. Contract families referenced

This map references the following contract families. Exact files and ownership
are listed in `docs/contracts/contracts-index-v1.1.md`.

- common
- execution
- artifacts
- cache
- visuals
- datasets
- lineage
- schemas
- semantics
- quality
- profiling
- associations
- joins
- features
- statistics
- modeling
- validation
- reporting
- registry
- pipeline

## 6. Documentation-only status

This document is documentation-only. It does not:

- Define Pydantic field shapes beyond documentation-level names.
- Introduce implementation code or tests.
- Freeze public data shapes that conflict with later contract tasks.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.

If a later contract task requires a shape incompatible with this map, the
conflict is resolved by an explicit task that updates this document minimally;
Build Queue v2.1 and actual repo state win.

## 7. Compatibility expectations

Later contract tasks must produce contracts compatible with this map:

- One request type and one result type per stage unless explicitly split.
- Request/result objects are typed, serializable, and backend-neutral.
- Skipped and blocked stages are representable as typed `StageResult` records.
- Reporting consumes typed results only.
- Pipeline is the only cross-module orchestrator.
- No causal claims in MVP output.
- No raw Polars/Pandas/DuckDB/NumPy/SciPy/Statsmodels/Matplotlib objects in
  public fields.