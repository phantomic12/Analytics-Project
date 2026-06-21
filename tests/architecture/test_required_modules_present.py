"""Architecture test: required modules/contracts exist (Build Queue v2.1 Task 76).

This test enforces the contract-first discipline at the package level:
every contract module declared in ``docs/contracts/contracts-index-v1.1.md``
whose Build Queue v2.1 task has landed must be importable from
``analytics_platform.contracts``. As Build Queue tasks land, the
``EXPECTED_MODULES`` list in this test grows; missing modules are
surfaced as test failures.

The test is intentionally *fail-loud*: a missing module produces a
clear ``ImportError`` failure that names the module and the Build
Queue task that should have produced it. The companion
``test_required_public_types`` test goes one step further and verifies
that the documented public types (per ``contracts-index-v1.1.md``)
are actually exposed by each present module.

This file lives under ``tests/architecture/`` (not
``tests/contracts/``) because the architecture-test plan in
``docs/testing/architecture-test-plan-v1.1.md`` owns this kind of
boundary check. The test deliberately avoids importing any heavy
compute library so that the import-weight guard at the bottom of
this file is the only thing it pulls in.
"""

from __future__ import annotations

import importlib

import pytest

import analytics_platform.contracts as contracts_pkg


# ---------------------------------------------------------------------------
# Module presence
# ---------------------------------------------------------------------------
# Per ``docs/contracts/contracts-index-v1.1.md`` section 3, every contract
# family declared in the index lives in its own module. This list is
# updated as Build Queue v2.1 contract tasks land; ordering matches the
# index. Adding a new module here is the canonical "Task 76 is
# satisfied" signal.
EXPECTED_MODULES: tuple[tuple[str, int], ...] = (
    # (module-name, build-queue-task-that-produced-it)
    ("common", 11),
    ("execution", 12),  # covers Tasks 12-14
    ("artifacts", 15),
    ("cache", 16),
    ("visuals", 17),
    ("datasets", 18),  # covers Tasks 18-20
    ("lineage", 21),
    ("schemas", 22),
    ("semantics", 23),
    ("quality", 24),
    ("profiling", 25),
    # --- Profile-only MVP checkpoint (Task 108) reached once the above are
    # present. The following modules are deferred to later tasks and are
    # NOT expected to exist yet:
    #   ("associations", 26),
    #   ("joins", 27),
    #   ("features", 28),  # covers Tasks 28-31
    #   ("statistics", 32),
    #   ("modeling", 33),  # covers Tasks 33-35
    #   ("validation", 36),  # covers Tasks 36-38
    #   ("reporting", 39),  # covers Tasks 39-40
    #   ("registry", 41),
    #   ("pipeline", 42),  # covers Tasks 42-45
)


class TestRequiredModulesPresent:
    @pytest.mark.parametrize(
        "module_name, build_queue_task",
        list(EXPECTED_MODULES),
    )
    def test_module_is_importable(
        self, module_name: str, build_queue_task: int
    ) -> None:
        """Every contract module listed in EXPECTED_MODULES must import.

        A failure here means a Build Queue v2.1 contract task is missing
        its module. The ``build_queue_task`` parameter names the task
        that should have produced the module so the failure is
        actionable.
        """
        fqmn = f"analytics_platform.contracts.{module_name}"
        try:
            importlib.import_module(fqmn)
        except ImportError as exc:  # pragma: no cover - failure path
            pytest.fail(
                f"Required contract module {fqmn!r} (Build Queue v2.1 "
                f"Task {build_queue_task}) is not importable: {exc}"
            )

    def test_unexpected_modules_are_documented(self) -> None:
        """The contracts package must not contain undocumented modules.

        Every ``analytics_platform.contracts.<name>`` module that
        exists on disk must appear in ``EXPECTED_MODULES`` (or in the
        deferred-comments list inside it). The "deferred" comment in
        the test is the single source of truth for which modules are
        not yet expected.
        """
        import pkgutil

        deferred: set[str] = {
            "associations",
            "joins",
            "features",
            "statistics",
            "modeling",
            "validation",
            "reporting",
            "registry",
            "pipeline",
        }
        expected = {name for name, _ in EXPECTED_MODULES}
        unexpected: list[str] = []
        for module_info in pkgutil.iter_modules(contracts_pkg.__path__):
            name = module_info.name
            if name in expected or name in deferred:
                continue
            unexpected.append(name)
        assert not unexpected, (
            "analytics_platform.contracts contains undocumented module(s): "
            f"{unexpected}. Add them to EXPECTED_MODULES (or the deferred "
            "set) in this test."
        )


# ---------------------------------------------------------------------------
# Public-type presence (per contracts-index-v1.1.md)
# ---------------------------------------------------------------------------
# Per-module minimum public types. These are the types listed in
# ``docs/contracts/contracts-index-v1.1.md`` table row for each family.
# Only public *names* are checked; specific field shapes are owned by
# the per-family contract tests.
REQUIRED_PUBLIC_TYPES: dict[str, tuple[str, ...]] = {
    "common": (
        "RunId",
        "DatasetId",
        "ModelId",
        "ReportId",
        "ArtifactId",
        "LineageId",
        "StageId",
        "Severity",
        "ExecutionStatus",
        "Issue",
        "WarningRecord",
        "MetricValue",
        "ArtifactRef",
        "StageResult",
    ),
    "execution": (
        "ExecutionBackend",
        "BackendId",
        "LazyFrameRef",
        "BackendObjectRef",
        "MaterializationRequest",
        "MaterializationResult",
        "MaterializationPolicy",
        "ExecutionLimitPolicy",
        "CollectPolicy",
        "PandasConversionPolicy",
        "MemoryBudgetPolicy",
    ),
    "artifacts": (
        "PersistedArtifact",
        "DatasetArtifactRef",
        "ArtifactStoragePolicy",
        "ArtifactHash",
    ),
    "cache": (
        "CacheKey",
        "CacheFingerprint",
        "CacheStatus",
        "InvalidationReason",
    ),
    "visuals": (
        "TableArtifactRef",
        "ChartArtifactRef",
        "VisualArtifactSpec",
    ),
    "datasets": (
        "DatasetFormat",
        "DatasetRole",
        "StorageBackend",
        "DatasetMaterializationStatus",
        "DatasetLoadRequest",
        "DatasetLoadResult",
        "DatasetHandle",
        "DatasetRef",
        "IngestionReport",
        "RegisteredDatasetResult",
        "DatasetFingerprint",
        "SourceFileMetadata",
    ),
    "lineage": (
        "LineageOperationType",
        "LineageRecord",
        "LineageGraphSnapshot",
        "SourceDatasetRef",
        "DerivedDatasetRef",
        "TransformationRef",
    ),
    "schemas": (
        "LogicalDataType",
        "PhysicalDataType",
        "ColumnSchema",
        "ObservedSchema",
        "ExpectedColumnSchema",
        "ExpectedSchema",
        "SchemaInferenceRequest",
        "SchemaValidationRequest",
        "SchemaValidationReport",
        "SchemaIssue",
    ),
    "semantics": (
        "SemanticColumnType",
        "ColumnRole",
        "SemanticTypeInferenceRequest",
        "SemanticTypeInferenceReport",
        "SemanticColumnProfile",
        "ColumnRoleAssignment",
        "SemanticTypeConfidence",
        "RiskyColumnUse",
    ),
    "quality": (
        "DataQualityReport",
        "MissingDataReport",
        "ColumnMissingness",
        "RowMissingnessSummary",
        "MissingnessPatternSummary",
        "JoinIntroducedMissingness",
        "ModelExclusionSummary",
        "DataQualityIssue",
    ),
    "profiling": (
        "ProfilingSpec",
        "ProfilingRequest",
        "DatasetProfile",
        "ColumnProfile",
        "NumericProfile",
        "CategoricalProfile",
        "DatetimeProfile",
        "MissingnessProfile",
        "CardinalityProfile",
        "DuplicateProfile",
        "OutlierProfile",
        "ProfileComputationMode",
        "ProfileApproximationMethod",
        "DistributionSummary",
        "QuantileSummary",
        "FrequencySummary",
        "ConstantColumnWarning",
        "HighCardinalityWarning",
    ),
}


class TestRequiredPublicTypes:
    @pytest.mark.parametrize(
        "module_name, type_names",
        list(REQUIRED_PUBLIC_TYPES.items()),
    )
    def test_module_exposes_documented_types(
        self, module_name: str, type_names: tuple[str, ...]
    ) -> None:
        fqmn = f"analytics_platform.contracts.{module_name}"
        try:
            module = importlib.import_module(fqmn)
        except ImportError as exc:  # pragma: no cover - parallel to test above
            pytest.fail(
                f"Required contract module {fqmn!r} is not importable: {exc}"
            )
        missing: list[str] = [
            name for name in type_names if not hasattr(module, name)
        ]
        assert not missing, (
            f"Contract module {fqmn!r} is missing documented public types: "
            f"{missing}. See docs/contracts/contracts-index-v1.1.md."
        )


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_contracts_package_still_dependency_light() -> None:
    """The architecture-test module must not pull heavy libs transitively.

    This test only imports ``analytics_platform.contracts`` (and
    ``pkgutil``), so the import-weight guard is a defense-in-depth check
    that the contract-first discipline still holds at the package
    level.
    """
    import sys

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported transitively: {leaked}"
