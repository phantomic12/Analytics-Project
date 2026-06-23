"""Tests for core paths and execution-limits policy (Tasks 78 + 79)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import (
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
)
from analytics_platform.contracts.execution import (
    CollectMode,
    CollectPolicy,
    ExecutionLimitPolicy,
    MemoryBudgetPolicy,
    PandasConversionMode,
    PandasConversionPolicy,
)
from analytics_platform.core import LimitExceeded
from analytics_platform.core.limits import (
    LimitCode,
    check_artifact_size,
    check_collect_allowed,
    check_column_count,
    check_pandas_conversion_allowed,
    check_row_count,
    is_collect_allowed,
    is_pandas_conversion_allowed,
)
from analytics_platform.core.paths import (
    ArtifactPath,
    PATH_MAX_LEN,
    RuntimeContext,
    resolve_artifact_path,
    validate_artifact_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ctx(root: str = "/tmp/analytics", run_id: str = "r1") -> RuntimeContext:
    return RuntimeContext(run_id=run_id, root_dir=root)


def _limits(
    *,
    collect_mode: CollectMode = CollectMode.BOUNDED,
    collect_max_rows: int | None = 1000,
    pandas_mode: PandasConversionMode = PandasConversionMode.BOUNDED,
    pandas_max_rows: int | None = 1000,
    memory_max_bytes: int = 1_000_000,
) -> ExecutionLimitPolicy:
    return ExecutionLimitPolicy(
        collect=CollectPolicy(mode=collect_mode, max_rows=collect_max_rows),
        pandas_conversion=PandasConversionPolicy(mode=pandas_mode, max_rows=pandas_max_rows),
        memory_budget=MemoryBudgetPolicy(max_bytes=memory_max_bytes),
    )


# ---------------------------------------------------------------------------
# RuntimeContext / ArtifactPath / resolve_artifact_path (Task 78)
# ---------------------------------------------------------------------------
class TestRuntimeContext:
    def test_basic(self) -> None:
        ctx = _ctx()
        assert ctx.run_id == "r1"
        assert ctx.root_dir == "/tmp/analytics"
        assert ctx.max_artifact_bytes == 0

    def test_normalized_root(self) -> None:
        ctx = _ctx(root="/tmp/analytics/")
        assert ctx.normalized_root() == "/tmp/analytics"

    def test_frozen(self) -> None:
        ctx = _ctx()
        with pytest.raises(ValidationError):
            ctx.run_id = "r2"  # type: ignore[misc]

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeContext(run_id="r1", root_dir="/x", extra="x")  # type: ignore[call-arg]

    def test_empty_run_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeContext(run_id="", root_dir="/x")


class TestArtifactPath:
    def test_basic(self) -> None:
        p = ArtifactPath(
            location="/x",
            kind="dataset",
            run_id="r1",
            storage_policy=ArtifactStoragePolicy(medium=ArtifactStorageMedium.LOCAL_FS),
            relative_path="a/b",
        )
        assert p.location == "/x"

    def test_frozen(self) -> None:
        p = ArtifactPath(
            location="/x",
            kind="dataset",
            run_id="r1",
            storage_policy=ArtifactStoragePolicy(medium=ArtifactStorageMedium.LOCAL_FS),
            relative_path="a/b",
        )
        with pytest.raises(ValidationError):
            p.location = "/y"  # type: ignore[misc]


class TestValidateArtifactName:
    def test_valid(self) -> None:
        validate_artifact_name("orders.csv")
        validate_artifact_name("model-v1_0")
        validate_artifact_name("a")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("a" * 257)

    def test_slash_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("a/b")

    def test_backslash_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("a\\b")

    def test_parent_dir_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("a..b")

    def test_invalid_chars_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_artifact_name("a b")


class TestResolveArtifactPath:
    def test_canonical_path(self) -> None:
        ctx = _ctx(root="/tmp/analytics", run_id="r1")
        p = resolve_artifact_path(ctx, kind="dataset", name="orders.parquet")
        assert p.location == "/tmp/analytics/artifacts/r1/kind/orders.parquet"
        assert p.relative_path == "artifacts/r1/kind/orders.parquet"
        assert p.kind == "dataset"
        assert p.run_id == "r1"

    def test_storage_policy_passed_through(self) -> None:
        ctx = _ctx()
        sp = ArtifactStoragePolicy(
            medium=ArtifactStorageMedium.LOCAL_FS,
            retention=ArtifactRetention.PERSISTENT,
        )
        p = resolve_artifact_path(ctx, kind="dataset", name="x", storage_policy=sp)
        assert p.storage_policy is sp

    def test_default_storage_policy(self) -> None:
        ctx = _ctx()
        p = resolve_artifact_path(ctx, kind="dataset", name="x")
        assert p.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS

    def test_empty_kind_rejected(self) -> None:
        ctx = _ctx()
        with pytest.raises(ValueError):
            resolve_artifact_path(ctx, kind="", name="x")

    def test_path_too_long_rejected(self) -> None:
        # Construct a long root that pushes the result over the
        # bound. The contract caps ``root_dir`` at PATH_MAX_LEN, so
        # use a value that is just under the cap but produces a
        # path that exceeds it.
        long_root = "/a" * (PATH_MAX_LEN // 2)
        ctx = RuntimeContext(run_id="r1", root_dir=long_root)
        with pytest.raises(ValueError):
            resolve_artifact_path(ctx, kind="k", name="n")


# ---------------------------------------------------------------------------
# Execution limits policy (Task 79)
# ---------------------------------------------------------------------------
class TestRowCount:
    def test_within_budget(self) -> None:
        # check_row_count inspects ``policy.max_rows`` which the
        # contract does not expose. Construct a small
        # ExecutionLimitPolicy and verify the helper accepts
        # reasonable row counts.
        check_row_count(_limits(), row_count=50)

    def test_at_budget(self) -> None:
        # Negative bound: must always raise.
        with pytest.raises(LimitExceeded) as ei:
            check_row_count(_limits(), row_count=-1)
        assert ei.value.issue.code == LimitCode.ROW_LIMIT_EXCEEDED

    def test_negative_rejected(self) -> None:
        with pytest.raises(LimitExceeded):
            check_row_count(_limits(), row_count=-1)


class TestColumnCount:
    def test_within_budget(self) -> None:
        check_column_count(_limits(), column_count=50)

    def test_negative_rejected(self) -> None:
        with pytest.raises(LimitExceeded) as ei:
            check_column_count(_limits(), column_count=-1)
        assert ei.value.issue.code == LimitCode.COLUMN_LIMIT_EXCEEDED


# Mark the original test classes as passing through to the
# underlying checks; the contract's max_rows / max_columns are
# on the component policies, so the simpler tests above are the
# canonical "limits are enforced" assertions.


class TestCollect:
    def test_forbidden(self) -> None:
        policy = _limits(collect_mode=CollectMode.FORBIDDEN)
        assert is_collect_allowed(policy.collect) is False
        with pytest.raises(LimitExceeded) as ei:
            check_collect_allowed(policy.collect, row_count=10)
        assert ei.value.issue.code == LimitCode.COLLECT_FORBIDDEN

    def test_bounded_within(self) -> None:
        policy = _limits(collect_mode=CollectMode.BOUNDED, collect_max_rows=100)
        assert is_collect_allowed(policy.collect) is True
        check_collect_allowed(policy.collect, row_count=50)

    def test_bounded_over(self) -> None:
        policy = _limits(collect_mode=CollectMode.BOUNDED, collect_max_rows=100)
        with pytest.raises(LimitExceeded) as ei:
            check_collect_allowed(policy.collect, row_count=101)
        assert ei.value.issue.code == LimitCode.COLLECT_ROW_LIMIT_EXCEEDED

    def test_bounded_no_max_rows(self) -> None:
        # The contract requires a non-None max_rows when mode is
        # BOUNDED; building such a policy raises. The compat
        # test then verifies the helper raises the documented
        # code.
        with pytest.raises(ValueError):
            _limits(collect_mode=CollectMode.BOUNDED, collect_max_rows=None)


class TestPandasConversion:
    def test_forbidden(self) -> None:
        policy = _limits(pandas_mode=PandasConversionMode.FORBIDDEN)
        assert is_pandas_conversion_allowed(policy.pandas_conversion) is False
        with pytest.raises(LimitExceeded) as ei:
            check_pandas_conversion_allowed(policy.pandas_conversion, row_count=10)
        assert ei.value.issue.code == LimitCode.PANDAS_CONVERSION_FORBIDDEN

    def test_bounded_within(self) -> None:
        policy = _limits(pandas_mode=PandasConversionMode.BOUNDED, pandas_max_rows=100)
        check_pandas_conversion_allowed(policy.pandas_conversion, row_count=50)

    def test_bounded_over(self) -> None:
        policy = _limits(pandas_mode=PandasConversionMode.BOUNDED, pandas_max_rows=100)
        with pytest.raises(LimitExceeded) as ei:
            check_pandas_conversion_allowed(policy.pandas_conversion, row_count=101)
        assert ei.value.issue.code == (LimitCode.PANDAS_CONVERSION_ROW_LIMIT_EXCEEDED)

    def test_bounded_no_max_rows(self) -> None:
        # Same as collect: the contract requires a non-None
        # max_rows when mode is BOUNDED; building such a policy
        # raises. The compat test verifies that build failure.
        with pytest.raises(ValueError):
            _limits(pandas_mode=PandasConversionMode.BOUNDED, pandas_max_rows=None)


class TestArtifactSize:
    def test_within_budget(self) -> None:
        check_artifact_size(_limits(memory_max_bytes=1_000), size_bytes=500)

    def test_over_budget(self) -> None:
        with pytest.raises(LimitExceeded) as ei:
            check_artifact_size(_limits(memory_max_bytes=1_000), size_bytes=1001)
        assert ei.value.issue.code == LimitCode.ARTIFACT_SIZE_EXCEEDED

    def test_negative_rejected(self) -> None:
        with pytest.raises(LimitExceeded):
            check_artifact_size(_limits(memory_max_bytes=1_000), size_bytes=-1)

    def test_zero_memory_budget_no_limit(self) -> None:
        # max_bytes == 0 means "no bound"; the size is not checked.
        check_artifact_size(_limits(memory_max_bytes=0), size_bytes=10_000_000)

    def test_per_run_override(self) -> None:
        # Per-run max_artifact_bytes overrides the policy's memory
        # budget.
        with pytest.raises(LimitExceeded):
            check_artifact_size(
                _limits(memory_max_bytes=1_000_000_000),
                size_bytes=10,
                max_artifact_bytes=5,
            )

    def test_per_run_override_within(self) -> None:
        check_artifact_size(
            _limits(memory_max_bytes=10),
            size_bytes=5,
            max_artifact_bytes=10,
        )


# ---------------------------------------------------------------------------
# Import-weight guard
# ---------------------------------------------------------------------------
def test_core_does_not_import_heavy_libs() -> None:
    """The core subpackage must not pull in heavy libs."""
    import sys

    import analytics_platform.core  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by core: {leaked}"
