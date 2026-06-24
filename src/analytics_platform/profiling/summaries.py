"""Numeric/categorical/datetime profiling summaries (Task 94).

Computes profiling summaries from column-major data and emits contract-
aligned DatasetProfile objects. Uses stdlib only; no numeric stack.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any, Mapping, Sequence

from analytics_platform.contracts.common import Issue, RunId, Severity, StageId
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.profiling import (
    CardinalityProfile,
    CategoricalProfile,
    ColumnProfile,
    ConstantColumnWarning,
    DatasetProfile,
    DatetimeProfile,
    DistributionSummary,
    FrequencySummary,
    HighCardinalityWarning,
    MissingnessProfile,
    NumericProfile,
    OutlierDetectionMethod,
    OutlierProfile,
    ProfileComputationMode,
    ProfilingSpec,
    QuantileSummary,
)
from analytics_platform.contracts.schemas import ObservedSchema
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = ["ProfilingSummaryComputer", "ProfilingSummaryError", "compute_summaries"]

_LOGGER = get_logger(__name__)


def _issue(code: str, message: str, *, run_id: RunId | None = None, stage_id: StageId | None = None) -> Issue:
    return Issue(code=code, severity=Severity.ERROR, message=message, run_id=run_id, stage_id=stage_id)


class ProfilingSummaryError(AnalyticsPlatformError):
    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class ProfilingSummaryComputer:
    def __init__(self, *, execution_limits: ExecutionLimitPolicy | None = None, spec: ProfilingSpec | None = None) -> None:
        self.execution_limits = execution_limits
        self.spec = spec or ProfilingSpec()

    def compute(
        self,
        data: Mapping[str, Sequence[Any]],
        *,
        observed: ObservedSchema | None = None,
        dataset: DatasetHandle | None = None,
        run_id: RunId | None = None,
        stage_id: StageId | None = None,
    ) -> DatasetProfile:
        if not data:
            raise ProfilingSummaryError(_issue("PROFILING_EMPTY_DATA", "Cannot profile empty data.", run_id=run_id, stage_id=stage_id))

        total_rows = len(next(iter(data.values())))
        self._check_limits(total_rows, len(data), run_id, stage_id)

        column_profiles = []
        constant_warnings = []
        cardinality_warnings = []
        for column_name, values in data.items():
            column_profile, const_warn, card_warn = self._profile_column(column_name, values, run_id, stage_id)
            column_profiles.append(column_profile)
            if const_warn:
                constant_warnings.append(const_warn)
            if card_warn:
                cardinality_warnings.append(card_warn)

        return DatasetProfile(
            dataset=dataset or DatasetHandle(dataset_id="dataset", dataset_ref="dataset-v1", name="dataset"),
            computation_mode=ProfileComputationMode.EXACT,
            column_profiles=tuple(column_profiles),
            constant_column_warnings=tuple(constant_warnings),
            high_cardinality_warnings=tuple(cardinality_warnings),
            run_id=run_id,
            stage_id=stage_id,
        )

    def _check_limits(self, total_rows: int, column_count: int, run_id: RunId | None, stage_id: StageId | None) -> None:
        policy = self.execution_limits
        if policy is None:
            return
        if policy.collect and policy.collect.mode == "bounded" and policy.collect.max_rows is not None and total_rows > policy.collect.max_rows:
            raise ProfilingSummaryError(_issue("PROFILING_LIMIT_MAX_ROWS", f"Exceeded collect max_rows={policy.collect.max_rows}.", run_id=run_id, stage_id=stage_id))
        if policy.pandas_conversion and policy.pandas_conversion.mode == "bounded" and policy.pandas_conversion.max_columns is not None and column_count > policy.pandas_conversion.max_columns:
            raise ProfilingSummaryError(_issue("PROFILING_LIMIT_MAX_COLUMNS", f"Exceeded pandas max_columns={policy.pandas_conversion.max_columns}.", run_id=run_id, stage_id=stage_id))

    def _profile_column(self, column_name: str, values: Sequence[Any], run_id: RunId | None, stage_id: StageId | None):
        non_null = [v for v in values if v is not None]
        missing_count = len(values) - len(non_null)
        missing_ratio = missing_count / len(values) if values else 0.0
        distinct_count = len(set(non_null))
        total_count = len(values)

        missingness = MissingnessProfile(missing_count=missing_count, total_count=total_count, missing_ratio=missing_ratio)
        cardinality = CardinalityProfile(distinct_count=distinct_count, total_count=total_count)
        outliers = OutlierProfile(method=OutlierDetectionMethod.NONE)

        if not non_null:
            return (
                ColumnProfile(column_name=column_name, missingness=missingness, cardinality=cardinality, outliers=outliers, computation_mode=ProfileComputationMode.EXACT),
                None,
                None,
            )

        first = non_null[0]
        if isinstance(first, (int, float)) and not isinstance(first, bool):
            numeric = self._numeric_profile(non_null)
            column = ColumnProfile(column_name=column_name, missingness=missingness, cardinality=cardinality, outliers=outliers, numeric=numeric, computation_mode=ProfileComputationMode.EXACT)
            return column, None, None

        if isinstance(first, datetime):
            datetime_profile = self._datetime_profile(non_null)
            column = ColumnProfile(column_name=column_name, missingness=missingness, cardinality=cardinality, outliers=outliers, datetime=datetime_profile, computation_mode=ProfileComputationMode.EXACT)
            return column, None, None

        categorical = self._categorical_profile(non_null)
        column = ColumnProfile(column_name=column_name, missingness=missingness, cardinality=cardinality, outliers=outliers, categorical=categorical, computation_mode=ProfileComputationMode.EXACT)
        const_warn = None
        if distinct_count == 1:
            const_warn = _constant_column_warning(column_name, non_null[0], len(non_null))
        card_warn = None
        if distinct_count > 50:
            card_warn = _high_cardinality_warning(column_name, distinct_count, total_count)
        return column, const_warn, card_warn

    def _numeric_profile(self, values: Sequence[float]) -> NumericProfile:
        finite = [float(v) for v in values]
        mean = sum(finite) / len(finite)
        variance = sum((v - mean) * (v - mean) for v in finite) / len(finite)
        std = math.sqrt(variance)
        quantiles = _linear_quantiles(finite, (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0))
        return NumericProfile(distribution=DistributionSummary(min=min(finite), max=max(finite), mean=mean, stddev=std, quantiles=quantiles, profiling_method="exact"))

    def _datetime_profile(self, values: Sequence[datetime]) -> DatetimeProfile:
        min_value = min(values)
        max_value = max(values)
        counter = Counter(v.year for v in values)
        entries = tuple(sorted(((str(k), v) for k, v in counter.items()), key=lambda x: x[0]))
        freqs = FrequencySummary(entries=entries, truncated=False)
        return DatetimeProfile(min=min_value, max=max_value, distinct_count=len(set(values)), bucket_frequencies=freqs, bucket_label="year")

    def _categorical_profile(self, values: Sequence[Any]) -> CategoricalProfile:
        counter = Counter(values)
        top = counter.most_common()
        entries = tuple((str(v), c) for v, c in top)
        freqs = FrequencySummary(entries=entries, total_count=len(values), truncated=False)
        return CategoricalProfile(top_frequencies=freqs, distinct_count=len(counter), most_frequent_value=str(top[0][0]), most_frequent_count=top[0][1], least_frequent_count=top[-1][1])


def _constant_column_warning(column_name: str, value: Any, count: int) -> ConstantColumnWarning:
    return ConstantColumnWarning(column_name=column_name, value=str(value), row_count=count, severity=Severity.WARNING)


def _high_cardinality_warning(column_name: str, distinct_count: int, total_count: int) -> HighCardinalityWarning:
    return HighCardinalityWarning(column_name=column_name, distinct_count=distinct_count, total_count=total_count, distinct_ratio=distinct_count / total_count, threshold_ratio=0.5, severity=Severity.WARNING)


def _linear_quantiles(values: Sequence[float], fractions: Sequence[float]) -> QuantileSummary:
    if not values:
        return QuantileSummary(quantile_pairs=((1.0, 0.0),), profiling_method="empty")
    ordered = sorted(values)
    pairs = []
    for q in sorted(fractions):
        if q <= 0.0:
            continue
        if q > 1.0:
            continue
        pos = (len(ordered) - 1) * q
        lower = int(math.floor(pos))
        upper = min(lower + 1, len(ordered) - 1)
        weight = pos - lower
        value = ordered[lower] * (1 - weight) + ordered[upper] * weight
        pairs.append((q, value))
    return QuantileSummary(quantile_pairs=tuple(pairs), profiling_method="linear")


def compute_summaries(
    data: Mapping[str, Sequence[Any]],
    *,
    observed: ObservedSchema | None = None,
    dataset: DatasetHandle | None = None,
    execution_limits: ExecutionLimitPolicy | None = None,
    spec: ProfilingSpec | None = None,
    run_id: RunId | None = None,
    stage_id: StageId | None = None,
) -> DatasetProfile:
    return ProfilingSummaryComputer(execution_limits=execution_limits, spec=spec).compute(data, observed=observed, dataset=dataset, run_id=run_id, stage_id=stage_id)
