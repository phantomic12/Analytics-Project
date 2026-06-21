"""analytics_platform.contracts subpackage.

Public re-exports for the analytics_platform contract families. Each
contract family is implemented in its own module so that the dependency
graph and build order remain explicit; this ``__init__`` simply gathers
the stable, public names into a single import surface once a family is
ready to be consumed.

Contract-first rule: this subpackage must not import any heavy
implementation library (no ``polars``, ``pandas``, ``duckdb``, ``numpy``,
``scipy``, ``statsmodels``, ``matplotlib``), and must not import any
domain implementation module (``core``, ``reporting``, ``pipeline``,
``cli``). It exposes typed, serializable, backend-neutral shapes only.

Build order and family ownership follow ``docs/contracts/contracts-index-v1.1.md``:

- ``common`` (Task 11) - base IDs, status, issues, warnings, metrics,
  artifacts, and ``StageResult``.
- ``execution`` (Tasks 12-14) - backend-neutral execution references,
  materialization, and limit policies.
- ``artifacts`` (Task 15) - durable artifact references and storage
  policy.
- ``cache`` (Task 16) - cache keys, fingerprints, and invalidation
  reasons.
- ``visuals`` (Task 17) - table/chart artifact references.
- ``datasets`` (Tasks 18-20) - dataset identity, load, ingestion, and
  fingerprint contracts.
- ``lineage`` (Task 21) - lineage records, references, and graph
  snapshots.
- ``schemas`` (Task 22) - schema inference and validation.
- ``semantics`` (Task 23) - semantic column typing.
- ``quality`` (Task 24) - data quality and missingness.
- ``profiling`` (Task 25) - distribution profiles.
- ``associations`` (Task 26) - diagnostic association checks.
- ``joins`` (Task 27) - join validation and execution.
- ``features`` (Tasks 28-31) - target/feature spec, transformations,
  matrix ref, and leakage checks.

Later families (statistics, modeling, validation, reporting,
registry, pipeline) are re-exported here only once their Build
Queue contract tasks land.
"""

from __future__ import annotations

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactStoragePolicy,
    DatasetArtifactRef,
    PersistedArtifact,
)
from analytics_platform.contracts.cache import (
    CacheFingerprint,
    CacheKey,
    CacheStatus,
    InvalidationReason,
)
from analytics_platform.contracts.common import (
    ArtifactId,
    ArtifactRef,
    DatasetId,
    ExecutionStatus,
    Issue,
    LineageId,
    MetricValue,
    ModelId,
    ReportId,
    RunId,
    Severity,
    StageId,
    StageResult,
    WarningRecord,
)
from analytics_platform.contracts.datasets import (
    DatasetFingerprint,
    DatasetFormat,
    DatasetHandle,
    DatasetLoadRequest,
    DatasetLoadResult,
    DatasetMaterializationStatus,
    DatasetRef,
    DatasetRole,
    IngestionReport,
    RegisteredDatasetResult,
    SourceFileMetadata,
    StorageBackend,
)
from analytics_platform.contracts.execution import (
    BackendId,
    BackendObjectRef,
    CollectMode,
    CollectPolicy,
    ExecutionBackend,
    ExecutionLimitPolicy,
    LazyFrameRef,
    MaterializationPolicy,
    MaterializationRequest,
    MaterializationResult,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)
from analytics_platform.contracts.lineage import (
    DerivedDatasetRef,
    LineageGraphSnapshot,
    LineageOperationType,
    LineageRecord,
    SourceDatasetRef,
    TransformationId,
    TransformationRef,
)
from analytics_platform.contracts.profiling import (
    CardinalityProfile,
    CategoricalProfile,
    ColumnProfile,
    ConstantColumnWarning,
    DatasetProfile,
    DatetimeProfile,
    DistributionSummary,
    DuplicateProfile,
    FrequencySummary,
    HighCardinalityWarning,
    MissingnessProfile,
    NumericProfile,
    OutlierDetectionMethod,
    OutlierProfile,
    ProfileApproximationMethod,
    ProfileComputationMode,
    ProfilingRequest,
    ProfilingSpec,
    QuantileSummary,
)
from analytics_platform.contracts.quality import (
    ColumnMissingness,
    DataQualityIssue,
    DataQualityIssueKind,
    DataQualityReport,
    JoinIntroducedMissingness,
    MissingDataReport,
    MissingnessPatternSummary,
    ModelExclusionReason,
    ModelExclusionSummary,
    RowMissingnessSummary,
)
from analytics_platform.contracts.schemas import (
    ColumnName,
    ColumnSchema,
    ExpectedColumnSchema,
    ExpectedSchema,
    LogicalDataType,
    ObservedSchema,
    PhysicalDataType,
    SchemaInferenceRequest,
    SchemaIssue,
    SchemaValidationReport,
    SchemaValidationRequest,
)
from analytics_platform.contracts.semantics import (
    ColumnRole,
    ColumnRoleAssignment,
    RiskyColumnUse,
    SemanticColumnProfile,
    SemanticColumnType,
    SemanticTypeConfidence,
    SemanticTypeInferenceReport,
    SemanticTypeInferenceRequest,
)
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    TableArtifactRef,
    VisualArtifactSpec,
)
from analytics_platform.contracts.associations import (
    AssociationCheckReport,
    AssociationCheckRequest,
    AssociationCheckSpec,
    AssociationWarning,
    CorrelationMethod,
    MulticollinearityRiskSummary,
    PairwiseAssociationSummary,
)
from analytics_platform.contracts.features import (
    ColumnsExcludedReport,
    EncodingStrategy,
    FeatureBuildRequest,
    FeatureEligibilityReport,
    FeatureExclusionReason,
    FeatureMatrixRef,
    FeatureMatrixResult,
    FeatureSpec,
    FeatureTransformationPlan,
    FeatureTransformationReport,
    LeakageCheckReport,
    LeakageCheckRequest,
    LeakageRisk,
    LeakageRiskType,
    MissingValueStrategy,
    PreprocessingFitScope,
    RowsExcludedReport,
    ScalingStrategy,
    SplitSpec,
    SplitStrategy,
    TargetSpec,
    TargetTask,
)
from analytics_platform.contracts.joins import (
    ColumnConflictPolicy,
    DuplicateKeyPolicy,
    JoinApprovalStatus,
    JoinCardinality,
    JoinExecutionReport,
    JoinExecutionRequest,
    JoinKeySpec,
    JoinRiskLevel,
    JoinSpec,
    JoinType,
    JoinValidationReport,
    JoinValidationRequest,
    JoinedDatasetResult,
    NullKeyPolicy,
)

__all__ = [
    # common (Task 11)
    "ArtifactId",
    "ArtifactRef",
    "DatasetId",
    "ExecutionStatus",
    "Issue",
    "LineageId",
    "MetricValue",
    "ModelId",
    "ReportId",
    "RunId",
    "Severity",
    "StageId",
    "StageResult",
    "WarningRecord",
    # execution (Tasks 12-14)
    "BackendId",
    "BackendObjectRef",
    "CollectMode",
    "CollectPolicy",
    "ExecutionBackend",
    "ExecutionLimitPolicy",
    "LazyFrameRef",
    "MaterializationPolicy",
    "MaterializationRequest",
    "MaterializationResult",
    "MemoryBudgetPolicy",
    "PandasConversionMode",
    "PandasConversionPolicy",
    # artifacts (Task 15)
    "ArtifactHash",
    "ArtifactStoragePolicy",
    "DatasetArtifactRef",
    "PersistedArtifact",
    # cache (Task 16)
    "CacheFingerprint",
    "CacheKey",
    "CacheStatus",
    "InvalidationReason",
    # visuals (Task 17)
    "ChartArtifactRef",
    "TableArtifactRef",
    "VisualArtifactSpec",
    # datasets (Tasks 18-20)
    "DatasetFingerprint",
    "DatasetFormat",
    "DatasetHandle",
    "DatasetLoadRequest",
    "DatasetLoadResult",
    "DatasetMaterializationStatus",
    "DatasetRef",
    "DatasetRole",
    "IngestionReport",
    "RegisteredDatasetResult",
    "SourceFileMetadata",
    "StorageBackend",
    # lineage (Task 21)
    "DerivedDatasetRef",
    "LineageGraphSnapshot",
    "LineageOperationType",
    "LineageRecord",
    "SourceDatasetRef",
    "TransformationId",
    "TransformationRef",
    # schemas (Task 22)
    "ColumnName",
    "ColumnSchema",
    "ExpectedColumnSchema",
    "ExpectedSchema",
    "LogicalDataType",
    "ObservedSchema",
    "PhysicalDataType",
    "SchemaInferenceRequest",
    "SchemaIssue",
    "SchemaValidationReport",
    "SchemaValidationRequest",
    # semantics (Task 23)
    "ColumnRole",
    "ColumnRoleAssignment",
    "RiskyColumnUse",
    "SemanticColumnProfile",
    "SemanticColumnType",
    "SemanticTypeConfidence",
    "SemanticTypeInferenceReport",
    "SemanticTypeInferenceRequest",
    # quality (Task 24)
    "ColumnMissingness",
    "DataQualityIssue",
    "DataQualityIssueKind",
    "DataQualityReport",
    "JoinIntroducedMissingness",
    "MissingDataReport",
    "MissingnessPatternSummary",
    "ModelExclusionReason",
    "ModelExclusionSummary",
    "RowMissingnessSummary",
    # profiling (Task 25)
    "CardinalityProfile",
    "CategoricalProfile",
    "ColumnProfile",
    "ConstantColumnWarning",
    "DatasetProfile",
    "DatetimeProfile",
    "DistributionSummary",
    "DuplicateProfile",
    "FrequencySummary",
    "HighCardinalityWarning",
    "MissingnessProfile",
    "NumericProfile",
    "OutlierDetectionMethod",
    "OutlierProfile",
    "ProfileApproximationMethod",
    "ProfileComputationMode",
    "ProfilingRequest",
    "ProfilingSpec",
    "QuantileSummary",
    # associations (Task 26)
    "AssociationCheckReport",
    "AssociationCheckRequest",
    "AssociationCheckSpec",
    "AssociationWarning",
    "CorrelationMethod",
    "MulticollinearityRiskSummary",
    "PairwiseAssociationSummary",
    # joins (Task 27)
    "ColumnConflictPolicy",
    "DuplicateKeyPolicy",
    "JoinApprovalStatus",
    "JoinCardinality",
    "JoinExecutionReport",
    "JoinExecutionRequest",
    "JoinKeySpec",
    "JoinRiskLevel",
    "JoinSpec",
    "JoinType",
    "JoinValidationReport",
    "JoinValidationRequest",
    "JoinedDatasetResult",
    "NullKeyPolicy",
    # features (Tasks 28-31)
    "ColumnsExcludedReport",
    "EncodingStrategy",
    "FeatureBuildRequest",
    "FeatureEligibilityReport",
    "FeatureExclusionReason",
    "FeatureMatrixRef",
    "FeatureMatrixResult",
    "FeatureSpec",
    "FeatureTransformationPlan",
    "FeatureTransformationReport",
    "LeakageCheckReport",
    "LeakageCheckRequest",
    "LeakageRisk",
    "LeakageRiskType",
    "MissingValueStrategy",
    "PreprocessingFitScope",
    "RowsExcludedReport",
    "ScalingStrategy",
    "SplitSpec",
    "SplitStrategy",
    "TargetSpec",
    "TargetTask",
]
