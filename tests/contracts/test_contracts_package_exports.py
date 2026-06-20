"""Tests for the contracts package public surface (Build Queue v2.1 Task 46).

Verifies that ``analytics_platform.contracts`` exposes the documented stable
names for every contract family whose Build Queue v2.1 contract tasks have
landed, and that importing the subpackage does not pull in heavy compute
libraries (same discipline as the per-module guards).

These tests intentionally avoid importing any heavy compute library so that
they exercise the dependency-light contract surface only.
"""

from __future__ import annotations

import importlib

import pytest

import analytics_platform.contracts as contracts_pkg


# ---------------------------------------------------------------------------
# Public-name stability
# ---------------------------------------------------------------------------
EXPECTED_PUBLIC_NAMES: tuple[str, ...] = (
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
)


class TestPublicSurface:
    def test_all_documented_names_exported(self) -> None:
        for name in EXPECTED_PUBLIC_NAMES:
            assert hasattr(contracts_pkg, name), (
                f"analytics_platform.contracts is missing documented public "
                f"name: {name!r}"
            )

    def test_dunder_all_lists_all_documented_names(self) -> None:
        # ``__all__`` must include every documented name. It may also list
        # additional names (e.g. aliases) without breaking this check.
        missing = set(EXPECTED_PUBLIC_NAMES) - set(contracts_pkg.__all__)
        assert not missing, f"__all__ is missing documented names: {sorted(missing)}"

    def test_every_all_entry_resolves(self) -> None:
        for name in contracts_pkg.__all__:
            obj = getattr(contracts_pkg, name, None)
            assert obj is not None, f"{name!r} listed in __all__ but not exposed"


# ---------------------------------------------------------------------------
# Cross-module re-export parity
# ---------------------------------------------------------------------------
class TestReExportParity:
    """Names listed in ``contracts.__all__`` must be the *same objects* as
    the ones defined in their owning module. This guards against accidental
    shadowing or duplicate definitions in ``__init__.py``."""

    @pytest.mark.parametrize("name", list(EXPECTED_PUBLIC_NAMES))
    def test_name_matches_owning_module_object(self, name: str) -> None:
        # Map each public name to its owning contract module. New families
        # added to ``EXPECTED_PUBLIC_NAMES`` must also be added here.
        module_for_name = {
            # common
            "ArtifactId": "analytics_platform.contracts.common",
            "ArtifactRef": "analytics_platform.contracts.common",
            "DatasetId": "analytics_platform.contracts.common",
            "ExecutionStatus": "analytics_platform.contracts.common",
            "Issue": "analytics_platform.contracts.common",
            "LineageId": "analytics_platform.contracts.common",
            "MetricValue": "analytics_platform.contracts.common",
            "ModelId": "analytics_platform.contracts.common",
            "ReportId": "analytics_platform.contracts.common",
            "RunId": "analytics_platform.contracts.common",
            "Severity": "analytics_platform.contracts.common",
            "StageId": "analytics_platform.contracts.common",
            "StageResult": "analytics_platform.contracts.common",
            "WarningRecord": "analytics_platform.contracts.common",
            # execution
            "BackendId": "analytics_platform.contracts.execution",
            "BackendObjectRef": "analytics_platform.contracts.execution",
            "CollectMode": "analytics_platform.contracts.execution",
            "CollectPolicy": "analytics_platform.contracts.execution",
            "ExecutionBackend": "analytics_platform.contracts.execution",
            "ExecutionLimitPolicy": "analytics_platform.contracts.execution",
            "LazyFrameRef": "analytics_platform.contracts.execution",
            "MaterializationPolicy": "analytics_platform.contracts.execution",
            "MaterializationRequest": "analytics_platform.contracts.execution",
            "MaterializationResult": "analytics_platform.contracts.execution",
            "MemoryBudgetPolicy": "analytics_platform.contracts.execution",
            "PandasConversionMode": "analytics_platform.contracts.execution",
            "PandasConversionPolicy": "analytics_platform.contracts.execution",
            # artifacts
            "ArtifactHash": "analytics_platform.contracts.artifacts",
            "ArtifactStoragePolicy": "analytics_platform.contracts.artifacts",
            "DatasetArtifactRef": "analytics_platform.contracts.artifacts",
            "PersistedArtifact": "analytics_platform.contracts.artifacts",
            # cache
            "CacheFingerprint": "analytics_platform.contracts.cache",
            "CacheKey": "analytics_platform.contracts.cache",
            "CacheStatus": "analytics_platform.contracts.cache",
            "InvalidationReason": "analytics_platform.contracts.cache",
            # visuals
            "ChartArtifactRef": "analytics_platform.contracts.visuals",
            "TableArtifactRef": "analytics_platform.contracts.visuals",
            "VisualArtifactSpec": "analytics_platform.contracts.visuals",
            # datasets
            "DatasetFingerprint": "analytics_platform.contracts.datasets",
            "DatasetFormat": "analytics_platform.contracts.datasets",
            "DatasetHandle": "analytics_platform.contracts.datasets",
            "DatasetLoadRequest": "analytics_platform.contracts.datasets",
            "DatasetLoadResult": "analytics_platform.contracts.datasets",
            "DatasetMaterializationStatus": "analytics_platform.contracts.datasets",
            "DatasetRef": "analytics_platform.contracts.datasets",
            "DatasetRole": "analytics_platform.contracts.datasets",
            "IngestionReport": "analytics_platform.contracts.datasets",
            "RegisteredDatasetResult": "analytics_platform.contracts.datasets",
            "SourceFileMetadata": "analytics_platform.contracts.datasets",
            "StorageBackend": "analytics_platform.contracts.datasets",
        }
        module_name = module_for_name[name]
        owning_module = importlib.import_module(module_name)
        assert getattr(contracts_pkg, name) is getattr(owning_module, name), (
            f"{name!r} on contracts package is not the same object as the one "
            f"defined in {module_name}"
        )


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_contracts_package_does_not_import_heavy_libs() -> None:
    """Importing the contracts subpackage must not pull heavy libs.

    Mirrors the per-module guards. The contracts subpackage is the public
    surface used by downstream modules, so the discipline that applies to
    individual modules must also hold at the package level.
    """
    import sys

    import analytics_platform.contracts as contracts_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by contracts package: {leaked}"
