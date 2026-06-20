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

- ``common`` (Task 11) — base IDs, status, issues, warnings, metrics,
  artifacts, and ``StageResult``. Imported from
  ``analytics_platform.contracts.common``.
- ``execution`` (Tasks 12-14) - backend-neutral execution references,
  materialization, and limit policies. Imported from
  ``analytics_platform.contracts.execution``.
- ``artifacts`` (Task 15) — durable artifact references and storage
  policy. Imported from ``analytics_platform.contracts.artifacts``.
- ``cache`` (Task 16) — cache keys, fingerprints, and invalidation
  reasons. Imported from ``analytics_platform.contracts.cache``.
- ``visuals`` (Task 17) — table/chart artifact references. Imported from
  ``analytics_platform.contracts.visuals``.
- ``datasets`` (Tasks 18-20) - dataset identity, load, ingestion, and
  fingerprint contracts. Imported from
  ``analytics_platform.contracts.datasets``.

Later families (lineage, schemas, semantics, quality, profiling,
associations, joins, features, statistics, modeling, validation,
reporting, registry, pipeline) are re-exported here only once their
Build Queue contract tasks land.
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
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    TableArtifactRef,
    VisualArtifactSpec,
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
]
