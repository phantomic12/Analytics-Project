"""Tests for the quality / missingness stages (Build Queue v2.1 Tasks 92-93)."""

from __future__ import annotations

from typing import Any

import pytest

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    DatasetRole,
    StorageBackend,
)
from analytics_platform.contracts.quality import (
    DataQualityIssueKind,
    MissingDataReport,
    ModelExclusionReason,
)
from analytics_platform.contracts.schemas import ColumnName
from analytics_platform.quality import (
    DataQualityError,
    DataQualityReporter,
    MissingnessError,
    MissingnessReporter,
    compute_data_quality,
    compute_missingness,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="d1",
        dataset_ref=DatasetRef("ds-d1"),
        name="d1",
        format=DatasetFormat.PARQUET,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.MATERIALIZED,
    )


# ===========================================================================
# Task 92 — missingness
# ===========================================================================
class TestMissingnessReporter:
    def test_per_column_missingness(self) -> None:
        data = {"a": [1, None, 3], "b": [None, None, None]}
        report = compute_missingness(data)
        cm_a = next(c for c in report.column_missingness if c.column_name == "a")
        cm_b = next(c for c in report.column_missingness if c.column_name == "b")
        assert cm_a.missing_count == 1
        assert cm_a.missing_ratio == pytest.approx(1 / 3)
        assert cm_b.missing_count == 3
        assert cm_b.missing_ratio == 1.0

    def test_constant_column_flagged(self) -> None:
        data = {"a": [1, 1, 1]}
        report = compute_missingness(data)
        cm_a = report.column_missingness[0]
        assert cm_a.is_constant is True

    def test_non_constant_column_not_flagged(self) -> None:
        data = {"a": [1, 2, 3]}
        report = compute_missingness(data)
        assert report.column_missingness[0].is_constant is False

    def test_all_missing_column_not_constant(self) -> None:
        # An all-missing column cannot be proven constant from the
        # data alone; the reporter must not flag it as constant.
        data = {"a": [None, None, None]}
        report = compute_missingness(data)
        assert report.column_missingness[0].is_constant is False

    def test_row_summary(self) -> None:
        # Row 0: complete (a=1, b=2, c=3)  -> 0 missing
        # Row 1: 1 missing (b=None)
        # Row 2: 2 missing (a=None, b=None)
        data = {
            "a": [1, 1, None],
            "b": [2, None, None],
            "c": [3, 3, 3],
        }
        report = compute_missingness(data)
        assert report.row_summary.total_rows == 3
        assert report.row_summary.complete_rows == 1
        assert report.row_summary.min_missing_per_row == 0
        assert report.row_summary.max_missing_per_row == 2
        assert report.row_summary.mean_missing_per_row == pytest.approx(1.0)

    def test_row_histogram_is_strictly_increasing(self) -> None:
        data = {"a": [1, None, None, None]}
        report = compute_missingness(data)
        keys = [pair[0] for pair in report.row_summary.missing_per_row_histogram]
        assert keys == sorted(keys)
        assert len(set(keys)) == len(keys)

    def test_pattern_labels_sorted_by_count(self) -> None:
        data = {
            "a": [1, None, 1, None, 1, None],
            "b": [None, None, None, None, None, None],
        }
        report = compute_missingness(data)
        labels = [p[0] for p in report.pattern_summary.patterns]
        counts = [p[1] for p in report.pattern_summary.patterns]
        # All-missing rows dominate; sorted descending by count.
        assert counts == sorted(counts, reverse=True)
        assert "col_b_missing" in labels

    def test_pattern_labels_unique(self) -> None:
        data = {"a": [1, None, 1], "b": [None, 2, None]}
        report = compute_missingness(data)
        labels = [p[0] for p in report.pattern_summary.patterns]
        assert len(labels) == len(set(labels))

    def test_pattern_summary_truncates_to_max(self) -> None:
        # Synthesize enough distinct patterns to exceed max_patterns.
        data = {
            "a": [1, None, 1, None],
            "b": [None, 2, None, 2],
            "c": [None, None, 3, 3],
            "d": [4, 4, None, None],
        }
        reporter = MissingnessReporter(max_patterns=2)
        report = reporter.compute(data)
        assert len(report.pattern_summary.patterns) == 2
        assert report.pattern_summary.max_patterns == 2

    def test_pattern_summary_max_patterns_bounded_by_count(self) -> None:
        data = {"a": [1, 2]}
        reporter = MissingnessReporter(max_patterns=10)
        report = reporter.compute(data)
        assert len(report.pattern_summary.patterns) <= 2

    def test_negative_max_patterns_rejected(self) -> None:
        with pytest.raises(MissingnessError) as ei:
            MissingnessReporter(max_patterns=-1)
        assert ei.value.issue.code == "MISSINGNESS_BAD_MAX_PATTERNS"

    def test_empty_data_rejected(self) -> None:
        with pytest.raises(MissingnessError) as ei:
            compute_missingness({})
        assert ei.value.issue.code == "MISSINGNESS_EMPTY_DATA"

    def test_ragged_columns_rejected(self) -> None:
        data = {"a": [1, 2], "b": [1, 2, 3]}
        with pytest.raises(MissingnessError) as ei:
            compute_missingness(data)
        assert ei.value.issue.code == "MISSINGNESS_RAGGED_COLUMNS"

    def test_dataset_overrides_synthetic(self) -> None:
        data = {"a": [1, 2, 3]}
        report = compute_missingness(data, dataset=_handle())
        assert report.dataset.dataset_id == "d1"

    def test_uses_passed_dataset_when_given(self) -> None:
        data = {"a": [1, 2, 3]}
        custom = _handle().model_copy(update={"name": "custom"})
        report = compute_missingness(data, dataset=custom)
        assert report.dataset.name == "custom"


# ===========================================================================
# Task 93 — data quality
# ===========================================================================
class TestDataQualityReporter:
    def test_no_issues_when_data_is_clean(self) -> None:
        data = {"a": [1, 2, 3], "b": ["x", "y", "z"]}
        report = compute_data_quality(data)
        assert report.quality_issues == ()
        assert report.model_exclusions == ()
        assert report.is_passthrough_clean is None

    def test_high_missingness_triggers_warning(self) -> None:
        # Two distinct non-missing values so constant_column does
        # not also fire; the high-missingness exclusion is kept.
        data = {"a": [1, 2, None, None]}
        report = compute_data_quality(data)
        assert any(
            i.kind is DataQualityIssueKind.HIGH_MISSINGNESS for i in report.quality_issues
        )
        assert any(
            e.reason is ModelExclusionReason.HIGH_MISSINGNESS
            for e in report.model_exclusions
        )

    def test_constant_column_triggers_warning(self) -> None:
        data = {"a": [1, 1, 1]}
        report = compute_data_quality(data)
        assert any(
            i.kind is DataQualityIssueKind.CONSTANT_COLUMN for i in report.quality_issues
        )

    def test_near_constant_column_triggers_warning(self) -> None:
        # 99 values of 1, 1 value of 2 -> distinct ratio 2/100 = 0.02
        # which is <= 0.01 (1 - near_constant_ratio). Wait, default
        # near_constant_ratio=0.99, so threshold is 1-0.99=0.01.
        # ratio=0.02 > 0.01 -> not near-constant.
        # Use a column with 200 same values + 1 distinct -> ratio
        # 2/201 ~= 0.00995 <= 0.01 -> near-constant.
        data = {"a": [1] * 200 + [2]}
        report = compute_data_quality(data)
        assert any(
            i.kind is DataQualityIssueKind.NEAR_CONSTANT_COLUMN
            for i in report.quality_issues
        )

    def test_passthrough_clean_flag(self) -> None:
        # With only warnings, is_passthrough_clean=True.
        # Two distinct non-missing values so the constant-column
        # rule does not also fire.
        data = {"a": [1, 2, None, None]}  # high-missingness (warning)
        report = compute_data_quality(data)
        assert report.is_passthrough_clean is True

    def test_passes_missingness_report_through(self) -> None:
        data = {"a": [1, 2, 3]}
        mr = compute_missingness(data, dataset=_handle())
        report = compute_data_quality(data, missingness_report=mr)
        assert report.missing_data is mr
        assert report.dataset.dataset_id == "d1"

    def test_high_missingness_ratio_out_of_range(self) -> None:
        with pytest.raises(DataQualityError) as ei:
            DataQualityReporter(high_missingness_ratio=1.5)
        assert ei.value.issue.code == "QUALITY_BAD_HIGH_MISSINGNESS_RATIO"

    def test_high_missingness_ratio_negative(self) -> None:
        with pytest.raises(DataQualityError):
            DataQualityReporter(high_missingness_ratio=-0.1)

    def test_near_constant_ratio_out_of_range(self) -> None:
        with pytest.raises(DataQualityError) as ei:
            DataQualityReporter(near_constant_ratio=1.5)
        assert ei.value.issue.code == "QUALITY_BAD_NEAR_CONSTANT_RATIO"

    def test_high_missingness_ratio_zero_flags_all(self) -> None:
        data = {"a": [1, 2, 3]}  # No missingness
        reporter = DataQualityReporter(high_missingness_ratio=0.0)
        report = reporter.compute(data)
        # 0.0 missing_ratio is not >= 0.0 strictly... actually the
        # contract allows equality. So this column with no missingness
        # is flagged as high-missingness with ratio 0.0. Acceptable
        # because the threshold is 0 (every column with missingness
        # ratio >= 0 triggers, which is every column).
        assert any(
            i.kind is DataQualityIssueKind.HIGH_MISSINGNESS for i in report.quality_issues
        )

    def test_no_constant_column_flag_for_all_missing(self) -> None:
        data = {"a": [None, None, None]}
        report = compute_data_quality(data)
        assert not any(
            i.kind is DataQualityIssueKind.CONSTANT_COLUMN for i in report.quality_issues
        )

    def test_custom_thresholds(self) -> None:
        data = {"a": [1, 1, 1, 2]}  # 0% missingness
        reporter = DataQualityReporter(
            high_missingness_ratio=0.0,  # flag every column
            near_constant_ratio=0.5,  # flag if distinct ratio <= 0.5
        )
        report = reporter.compute(data)
        # distinct ratio = 2/4 = 0.5, threshold is 1-0.5=0.5 -> 0.5
        # is not strictly <= 0.5; we treat the test as boundary.
        # The reporter currently flags when ratio <= 1 - threshold,
        # so 0.5 <= 0.5 -> flagged.
        assert any(
            i.kind is DataQualityIssueKind.NEAR_CONSTANT_COLUMN
            for i in report.quality_issues
        )

    def test_no_passthrough_clean_flag_when_no_issues(self) -> None:
        data = {"a": [1, 2, 3]}
        report = compute_data_quality(data)
        assert report.is_passthrough_clean is None

    def test_uses_synthetic_dataset_when_missing(self) -> None:
        data = {"a": [1, 2, 3]}
        report = compute_data_quality(data)
        assert report.dataset.dataset_id == "unknown"

    def test_run_id_threads_through(self) -> None:
        from analytics_platform.contracts.common import RunId

        data = {"a": [1, 1, 1]}
        report = compute_data_quality(data, run_id=RunId("run-1"))
        assert any(i.run_id == RunId("run-1") for i in report.quality_issues)
        assert any(e.run_id == RunId("run-1") for e in report.model_exclusions)


class TestQualityReporterMisc:
    def test_missing_data_unchanged(self) -> None:
        data = {"a": [1, 2, 3]}
        mr = compute_missingness(data)
        report = compute_data_quality(data, missingness_report=mr)
        assert report.missing_data.column_missingness == mr.column_missingness

    def test_column_exclusions_unique(self) -> None:
        # The contract requires unique column names in
        # ``model_exclusions``. The reporter must not add the same
        # column twice even when it triggers multiple rules.
        data = {"a": [1, 1, 1, None, None]}
        report = compute_data_quality(data)
        names = [e.column_name for e in report.model_exclusions]
        # ``a`` triggers both constant-column and high-missingness;
        # both rules add an exclusion. The contract dedup validator
        # would catch duplicates; verify the reporter avoids them.
        assert len(names) == len(set(names))