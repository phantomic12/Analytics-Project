# Contracts Index v1.1

Status: Active for Build Queue v2.1 Task 6.
Owner: Analytics Platform Team.
Scope: index of contract families for the analytics-platform. This document
lists each family, its intended file/module, owned concepts, allowed consumers,
and sequencing expectations. It is documentation-only; implementation of the
referenced contracts comes later in Build Queue v2.1 contract tasks.

Companion docs (do not duplicate, refer to them):
- `docs/contracts/interface-map-v1.1.md` — stage-by-stage request/result flow.
- `docs/architecture/architecture-pack-v1.1.md` — module inventory.
- `docs/architecture/quantitative-analysis-design-v1.1.md` — v1.1 quantitative
  contract additions.
- `docs/architecture/dependency-rules-v1.1.md` — import layering and forbidden
  imports.
- `docs/architecture/statistical-validation-strategy-v1.1.md` — claim levels and
  validation doctrine.

## 1. Purpose

This index is the documentation-level source of truth for which contract family
owns which concepts, where the family lives, who may import it, and when it is
sequenced in the build queue. It does not:

- Freeze Pydantic field definitions beyond documentation-level
  responsibilities already present in upstream source docs.
- Introduce implementation code or tests.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Override `dependency-rules-v1.1.md` on import discipline.

If a later contract task requires a shape that conflicts with this index, the
conflict is resolved by an explicit task that updates this document minimally;
Build Queue v2.1 and actual repo state win.

## 2. Cross-cutting rules

All contract families share these rules, restated from
`dependency-rules-v1.1.md` and `statistical-validation-strategy-v1.1.md`:

- Contracts may import `pydantic`, the Python standard library, and other
  contracts only.
- Contracts must not import `polars`, `pandas`, `duckdb`, `numpy`, `scipy`,
  `statsmodels`, or `matplotlib`.
- Contracts must not import `core`, domain implementations, `reporting`,
  `pipeline`, or `cli`.
- Contracts must not contain raw dataframe, model, or matrix objects in public
  fields.
- Public objects are typed, serializable, and backend-neutral.
- Domain modules do not import `contracts/pipeline.py`.
- Pipeline is the only cross-module orchestrator.
- No causal claims in MVP output; causal claim levels are blocked in v1.1.

## 3. Contract families

The table below lists documentation-level responsibilities only. "Build Queue
tasks" refers to the Build Queue v2.1 task numbers that implement each family's
public contracts and tests.

| Family | Intended module | Owned concepts (documentation-level) | Allowed consumers | Build Queue tasks |
| --- | --- | --- | --- | --- |
| common | `contracts/common.py` | `RunId`, `DatasetId`, `ColumnName`, `ModelId`, `ReportId`, `ArtifactId`, `LineageId`, `StageId`, `Severity`, `ExecutionStatus`, `Issue`, `WarningRecord`, `MetricValue`, `ArtifactRef`, `StageResult`, `ContentHash`, `Timestamp`, `RandomSeed` | All modules | 11 |
| execution | `contracts/execution.py` | `ExecutionBackend`, `BackendId`, `LazyFrameRef`, `BackendObjectRef`, `MaterializationRequest`, `MaterializationResult`, `MaterializationPolicy`, `ExecutionLimitPolicy`, `CollectPolicy`, `PandasConversionPolicy`, `MemoryBudgetPolicy` | IO; catalog; backends; profiling; joins; features; modeling | 12–14 |
| artifacts | `contracts/artifacts.py` | `PersistedArtifact`, `DatasetArtifactRef`, `ArtifactStoragePolicy`, `ArtifactHash` | IO; catalog; reporting; registry; cache | 15 |
| cache | `contracts/cache.py` | `CacheKey`, `CacheFingerprint`, `CacheStatus`, `InvalidationReason` | Artifact store; manifest; registry; pipeline cache | 16 |
| visuals | `contracts/visuals.py` | `TableArtifactRef`, `ChartArtifactRef`, `VisualArtifactSpec` | Reporting; registry | 17 |
| datasets | `contracts/datasets.py` | `DatasetFormat`, `DatasetRole`, `StorageBackend`, `DatasetMaterializationStatus`, `DatasetLoadRequest`, `DatasetLoadResult`, `DatasetHandle`, `DatasetRef`, `IngestionReport`, `RegisteredDatasetResult`, `DatasetFingerprint`, `SourceFileMetadata` | IO; catalog; schema; profiling; joins; features | 18–20 |
| lineage | `contracts/lineage.py` | `LineageOperationType`, `LineageRecord`, `LineageGraphSnapshot`, `SourceDatasetRef`, `DerivedDatasetRef`, `TransformationRef` | catalog; joins; features; reporting; pipeline | 21 |
| schemas | `contracts/schemas.py` | `LogicalDataType`, `PhysicalDataType`, `ColumnSchema`, `ObservedSchema`, `ExpectedColumnSchema`, `ExpectedSchema`, `SchemaInferenceRequest`, `SchemaValidationRequest`, `SchemaValidationReport`, `SchemaIssue` | schema; semantics; quality; joins; features; reporting | 22 |
| semantics | `contracts/semantics.py` | `SemanticColumnType`, `ColumnRole`, `SemanticTypeInferenceRequest`, `SemanticTypeInferenceReport`, `SemanticColumnProfile`, `ColumnRoleAssignment`, `SemanticTypeConfidence`, `RiskyColumnUse` | schema; profiling; joins; features; modeling; validation; reporting | 23 |
| quality | `contracts/quality.py` | `DataQualityReport`, `MissingDataReport`, `ColumnMissingness`, `RowMissingnessSummary`, `MissingnessPatternSummary`, `JoinIntroducedMissingness`, `ModelExclusionSummary`, `DataQualityIssue` | schema; profiling; joins; features; modeling; validation; reporting | 24 |
| profiling | `contracts/profiling.py` | `ProfilingSpec`, `ProfilingRequest`, `DatasetProfile`, `ColumnProfile`, `NumericProfile`, `CategoricalProfile`, `DatetimeProfile`, `MissingnessProfile`, `CardinalityProfile`, `DuplicateProfile`, `OutlierProfile`, `ProfileComputationMode`, `ProfileApproximationMethod`, `DistributionSummary`, `QuantileSummary`, `FrequencySummary`, `ConstantColumnWarning`, `HighCardinalityWarning` | profiling; associations; joins; reporting | 25 |
| associations | `contracts/associations.py` | `AssociationCheckSpec`, `AssociationCheckRequest`, `AssociationCheckReport`, `PairwiseAssociationSummary`, `CorrelationMethod`, `AssociationWarning`, `MulticollinearityRiskSummary` | associations; features; modeling; validation; reporting | 26 |
| joins | `contracts/joins.py` | `JoinType`, `JoinCardinality`, `JoinRiskLevel`, `JoinApprovalStatus`, `ColumnConflictPolicy`, `NullKeyPolicy`, `DuplicateKeyPolicy`, `JoinSpec`, `JoinValidationRequest`, `JoinValidationReport`, `JoinExecutionRequest`, `JoinExecutionReport`, `JoinedDatasetResult` | joins; features; reporting; pipeline | 27 |
| features | `contracts/features.py` | `TargetSpec`, `FeatureSpec`, `SplitSpec`, `FeatureBuildRequest`, `FeatureMatrixRef`, `FeatureMatrixResult`, `LeakageCheckRequest`, `LeakageCheckReport`, `LeakageRisk`, `LeakageRiskType`, `MissingValueStrategy`, `EncodingStrategy`, `ScalingStrategy`, `SplitStrategy`, `FeatureTransformationPlan`, `FeatureTransformationReport`, `PreprocessingFitScope`, `RowsExcludedReport`, `ColumnsExcludedReport`, `FeatureEligibilityReport` | features; modeling; validation; reporting | 28–31 |
| statistics | `contracts/statistics.py` | `StatisticalTestResult`, `MultipleTestingCorrectionMethod`, `MultipleTestingCorrectionReport`, `TestFamily`, `PValueAdjustmentResult`, `EffectEstimate`, `ConfidenceInterval` | modeling; associations; validation; reporting | 32 |
| modeling | `contracts/modeling.py` | `ModelType`, `ModelFamily`, `TargetType`, `OLSModelSpec`, `ModelSpec`, `ModelSpecValidationReport`, `ModelPurpose`, `ModelFitRequest`, `ModelResult`, `ModelCoefficient`, `CoefficientTable`, `ModelMetricSet`, `ModelDiagnosticRequest`, `ModelDiagnosticReport`, `ModelFitSummary`, `ModelAssumptionDiagnostics`, `ModelDataDiagnostics`, `ModelStabilityDiagnostics`, `ModelInterpretationLimit`, `AssumptionCheckResult`, `OverfittingCheckResult` | modeling; validation; reporting | 33–35 |
| validation | `contracts/validation.py` | `ValidationSpec`, `ModelValidationRequest`, `ModelValidationReport`, `ValidatedModelInterpretation`, `RejectedModelInterpretation`, `EvidenceGrade`, `ClaimLevel`, `CausalClaimPolicy`, `CausalWarning`, `ApprovedWording`, `DisallowedWording`, `ValidationStrategy`, `RobustnessCheckSpec`, `RobustnessCheckResult`, `RobustnessCheckStatus`, `SkippedRobustnessCheck` | validation; reporting; pipeline | 36–38 |
| reporting | `contracts/reporting.py` | `ReportFormat`, `ReportSpec`, `ReportBuildRequest`, `ReportInputBundle`, `ReportSection`, `ReportSectionType`, `ReportRenderRequest`, `ReportArtifactSet`, `ReportWarningSummary`, `ReportClaimSummary` | reporting; pipeline; cli | 39–40 |
| registry | `contracts/registry.py` | `RunRegistryRecord`, `ResultRegistryEntry`, `ModelRegistryEntry`, `DatasetRegistryEntry`, `ArtifactRegistryEntry`, `RegistryWriteRequest`, `RegistryWriteResult`, `RunHistoryQuery` | registry; pipeline; cli; reporting (read-only refs only) | 41 |
| pipeline | `contracts/pipeline.py` | `AnalysisPlan`, `AnalysisRunResult`, `PipelineStageName`, `PipelineExecutionMode`, `PipelineFailurePolicy`, `RunManifestRequest`, `RunManifest`, `PipelineWarningSummary` | core.config; pipeline; cli | 42–45 |

## 4. Sequencing expectations

Contract implementation is sequenced by Build Queue v2.1 and is not started
before this index exists. The intended order is:

1. `common` (Task 11) — base IDs, status, issues, warnings, metrics, artifacts,
   and `StageResult`. All later families depend on this.
2. `execution` (Tasks 12–14) — backend-neutral execution references and limit
   policies, before any backend or dataset contract.
3. `artifacts` (Task 15) and `cache` (Task 16) — durable artifact references and
   cache invalidation, before datasets and registry.
4. `visuals` (Task 17) — table/chart artifact references, after artifacts.
5. `datasets` (Tasks 18–20) — handles, load, and fingerprints, after execution,
   artifacts, and cache.
6. `lineage` (Task 21) — lineage records, after datasets and artifacts.
7. `schemas` (Task 22) — schema inference and validation.
8. `semantics` (Task 23) — semantic column typing.
9. `quality` (Task 24) — data quality and missingness.
10. `profiling` (Task 25) — distribution profiles.
11. `associations` (Task 26) — diagnostic association reports.
12. `joins` (Task 27) — join validation and execution.
13. `features` (Tasks 28–31) — target/feature specs, transformations, matrix
    refs, and leakage.
14. `statistics` (Task 32) — shared statistical primitives.
15. `modeling` (Tasks 33–35) — model spec, result, and diagnostics.
16. `validation` (Tasks 36–38) — claim levels, model validation, robustness.
17. `reporting` (Tasks 39–40) — report sections, bundles, and artifacts.
18. `registry` (Task 41) — run/result registry contracts.
19. `pipeline` (Tasks 42–45) — stage names, analysis plan, manifest, run result.
20. Contract exports stabilization (Task 46).

The profile-only MVP checkpoint is Task 108. No joins, feature matrices,
modeling, full cache integration, chart generation, DuckDB implementation, or
history CLI begins before Task 108 passes.

## 5. Documentation-only status

This index is documentation-only. It does not:

- Define Pydantic field shapes beyond documentation-level responsibilities
  already present in upstream source docs.
- Introduce implementation code or tests.
- Freeze public data shapes that conflict with later contract tasks.
- Permit raw dataframes, model objects, or dictionaries across public
  boundaries.
- Override the import discipline in `dependency-rules-v1.1.md`.

## 6. Compatibility expectations

Later contract tasks must produce contracts compatible with this index:

- Each family owns exactly the concepts listed above unless a later task
  explicitly extends it.
- A concept is never invented in a second family if it already has a home here.
- Public objects are typed, serializable, and backend-neutral.
- No raw Polars/Pandas/DuckDB/NumPy/SciPy/Statsmodels/Matplotlib objects in
  public fields.
- Reporting imports contracts only, never domain implementations.
- Domain modules do not import `contracts/pipeline.py`.
- Causal claim levels remain blocked in v1.1 MVP output.