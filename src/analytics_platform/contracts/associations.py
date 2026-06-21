"""Diagnostic association contracts (Build Queue v2.1 Task 26).

Public contracts for the ``associations`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Association contracts
describe the typed output of stage 4.9 (diagnostic association checks).
Per the interface map, this stage is *diagnostic-only*: it never
produces an analytical finding. A perfect association is allowed to
trigger leakage re-checks downstream, but it does not, on its own,
produce a conclusion.

Contracts are dependency-light: they import ``pydantic``, the standard
library, and the shared ``common`` / ``schemas`` / ``semantics`` /
``profiling`` contracts only. They never embed raw dataframes, model
objects, sample values, or backend objects.

Scope:

- ``CorrelationMethod`` — catalogued correlation estimators.
- ``AssociationCheckSpec`` — bounded spec for what the stage computes.
- ``AssociationCheckRequest`` — request shape.
- ``AssociationCheckReport`` — top-level typed output.
- ``PairwiseAssociationSummary`` — per-pair summary row.
- ``MulticollinearityRiskSummary`` — typed multicollinearity advisory.
- ``AssociationWarning`` — typed per-warning record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.schemas import ColumnName

__all__ = [
    "CorrelationMethod",
    "AssociationCheckSpec",
    "AssociationCheckRequest",
    "AssociationCheckReport",
    "PairwiseAssociationSummary",
    "MulticollinearityRiskSummary",
    "AssociationWarning",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _AssociationsContractModel(BaseModel):
    """Base configuration for association contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, model objects,
    sample values, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded absolute correlation / score in [0.0, 1.0].
_BoundedAbsoluteScore = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# CorrelationMethod
# ===========================================================================
class CorrelationMethod(str, Enum):
    """Catalogued correlation estimators used in association diagnostics.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The enum is documentation-level; new methods
    may be added in later tasks.
    """

    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"
    CRAMERS_V = "cramers_v"
    PHI = "phi"
    POINT_BISERIAL = "point_biserial"
    UNKNOWN = "unknown"


# ===========================================================================
# AssociationCheckSpec
# ===========================================================================
class AssociationCheckSpec(_AssociationsContractModel):
    """A bounded spec for what the diagnostic association stage computes.

    Fields:

    - ``method``: :class:`CorrelationMethod` to use as the default
      (per-pair overrides are possible via ``PairwiseAssociationSummary``).
    - ``include_categorical``: when ``True``, the stage computes
      categorical-vs-categorical associations (e.g. ``CRAMERS_V``) in
      addition to numeric pairs. Defaults to ``True``.
    - ``max_pairs``: optional non-negative upper bound on the number
      of pairs to evaluate. ``None`` means "no bound".
    - ``min_abs_score_to_report``: optional bounded absolute score
      threshold in ``[0.0, 1.0]``. Pairs with absolute score below
      this are omitted from the report. Defaults to ``0.0`` (report
      all pairs).
    - ``max_unique_values_for_categorical``: optional non-negative
      upper bound on the unique-value count above which a categorical
      column is excluded from the categorical pass. Defaults to ``50``.
    - ``emit_multicollinearity_summary``: when ``True``, the stage
      includes a :class:`MulticollinearityRiskSummary`. Defaults to
      ``True``.
    """

    method: CorrelationMethod = Field(
        default=CorrelationMethod.PEARSON,
        description="Default CorrelationMethod for the diagnostic pass.",
    )
    include_categorical: bool = Field(
        default=True,
        description="When True, categorical-vs-categorical pairs are evaluated.",
    )
    max_pairs: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on the number of pairs to evaluate.",
    )
    min_abs_score_to_report: _BoundedAbsoluteScore = Field(
        default=0.0,
        description="Optional bounded absolute score threshold in [0.0, 1.0].",
    )
    max_unique_values_for_categorical: int = Field(
        default=50,
        ge=0,
        description="Optional non-negative upper bound on unique-value count for categorical columns.",
    )
    emit_multicollinearity_summary: bool = Field(
        default=True,
        description="When True, the report includes a MulticollinearityRiskSummary.",
    )


# ===========================================================================
# AssociationCheckRequest
# ===========================================================================
class AssociationCheckRequest(_AssociationsContractModel):
    """A typed request to run diagnostic association checks.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the dataset to inspect.
    - ``spec``: :class:`AssociationCheckSpec` (defaults to a spec
      with the documented defaults).
    - ``execution_limits``: :class:`ExecutionLimitPolicy` to apply.
    - ``target_column``: optional :data:`ColumnName` indicating the
      target column. When provided, the stage may emit target-vs-
      feature summaries in addition to pairwise summaries.
    - ``feature_columns``: optional tuple of :data:`ColumnName`
      indicating the feature columns to include. ``None`` means
      "all non-target columns".
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the dataset to inspect.",
    )
    spec: AssociationCheckSpec = Field(
        default_factory=AssociationCheckSpec,
        description="AssociationCheckSpec describing what to compute.",
    )
    execution_limits: ExecutionLimitPolicy = Field(
        ...,
        description="ExecutionLimitPolicy to apply during the diagnostic pass.",
    )
    target_column: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName of the target column.",
    )
    feature_columns: tuple[ColumnName, ...] = Field(
        default=(),
        description="Optional tuple of feature column names. Empty means 'all non-target columns'.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _target_not_in_feature_columns(self) -> "AssociationCheckRequest":
        if self.target_column is not None and self.target_column in self.feature_columns:
            raise ValueError(
                "AssociationCheckRequest.target_column must not also appear in feature_columns."
            )
        return self

    @model_validator(mode="after")
    def _feature_columns_unique(self) -> "AssociationCheckRequest":
        seen: set[str] = set()
        for col in self.feature_columns:
            if col in seen:
                raise ValueError(
                    f"AssociationCheckRequest.feature_columns has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


# ===========================================================================
# PairwiseAssociationSummary
# ===========================================================================
class PairwiseAssociationSummary(_AssociationsContractModel):
    """A single pairwise association summary row.

    Per the interface map (stage 4.9), association diagnostics are
    diagnostic-only. ``PairwiseAssociationSummary`` records a single
    pair, the method used, the bounded score, and an optional sample
    size. It must never carry raw column data, model objects, or
    sample values.

    Fields:

    - ``column_a`` / ``column_b``: the two column names. The
      constructor does not enforce ordering; the validator enforces
      ``column_a < column_b`` (lexicographic) so consumers can
      rely on a stable canonical form.
    - ``method``: :class:`CorrelationMethod` actually used (may
      differ from the spec default for categorical pairs).
    - ``score``: bounded absolute score in ``[0.0, 1.0]``.
    - ``sample_size``: optional non-negative sample size used.
    - ``is_perfect``: optional flag indicating the score is exactly
      ``1.0`` (a perfect association; downstream may use this to
      trigger leakage re-checks per stage 4.9).
    - ``is_constant_pair``: optional flag indicating at least one of
      the two columns is constant (which produces a degenerate
      score).
    - ``notes``: optional bounded human-readable note.
    """

    column_a: ColumnName = Field(..., description="ColumnName of the first column.")
    column_b: ColumnName = Field(..., description="ColumnName of the second column.")
    method: CorrelationMethod = Field(
        default=CorrelationMethod.PEARSON,
        description="CorrelationMethod actually used for this pair.",
    )
    score: _BoundedAbsoluteScore = Field(
        ...,
        description="Bounded absolute correlation score in [0.0, 1.0].",
    )
    sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative sample size used.",
    )
    is_perfect: bool | None = Field(
        default=None,
        description="Optional flag indicating the score is exactly 1.0 (a perfect association).",
    )
    is_constant_pair: bool | None = Field(
        default=None,
        description="Optional flag indicating at least one of the two columns is constant.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _columns_must_differ(self) -> "PairwiseAssociationSummary":
        if self.column_a == self.column_b:
            raise ValueError("PairwiseAssociationSummary.column_a and column_b must differ.")
        return self

    @model_validator(mode="after")
    def _columns_canonical_order(self) -> "PairwiseAssociationSummary":
        if self.column_a > self.column_b:
            # Swap so the pair is canonically ordered. Capture the
            # original column_a first because ``object.__setattr__``
            # mutates ``self.column_a`` before the second assignment
            # is evaluated.
            original_a = self.column_a
            object.__setattr__(self, "column_a", self.column_b)
            object.__setattr__(self, "column_b", original_a)
        return self

    @model_validator(mode="after")
    def _is_perfect_consistent_with_score(self) -> "PairwiseAssociationSummary":
        if self.is_perfect is True and self.score != 1.0:
            raise ValueError("PairwiseAssociationSummary with is_perfect=True must have score=1.0.")
        if self.is_perfect is False and self.score == 1.0:
            raise ValueError(
                "PairwiseAssociationSummary with is_perfect=False must not have score=1.0."
            )
        return self


# ===========================================================================
# AssociationWarning
# ===========================================================================
class AssociationWarning(_AssociationsContractModel):
    """A typed warning raised during the diagnostic association stage.

    Fields:

    - ``code``: stable machine-readable code.
    - ``severity``: :class:`Severity` of the warning.
    - ``message``: human-readable message.
    - ``column_a`` / ``column_b``: optional pair locator.
    - ``score``: optional bounded absolute score.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``context``: small bounded string-to-string metadata.
    """

    code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable warning code.",
    )
    severity: Severity = Field(..., description="Severity of the warning.")
    message: str = Field(..., min_length=1, description="Human-readable warning message.")
    column_a: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName of the first column.",
    )
    column_b: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName of the second column.",
    )
    score: _BoundedAbsoluteScore | None = Field(
        default=None,
        description="Optional bounded absolute score in [0.0, 1.0].",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# MulticollinearityRiskSummary
# ===========================================================================
class MulticollinearityRiskSummary(_AssociationsContractModel):
    """A typed multicollinearity advisory.

    Per the interface map, multicollinearity diagnostics are
    diagnostic-only. ``MulticollinearityRiskSummary`` records the
    column set, the bounded high-risk threshold, the count of
    high-risk pairs, and an optional tuple of high-risk pair
    columns. It must not produce an analytical finding on its own.

    Fields:

    - ``high_risk_threshold``: bounded absolute score in
      ``[0.0, 1.0]`` above which a pair is considered high-risk.
    - ``high_risk_pair_count``: optional non-negative count of
      high-risk pairs.
    - ``high_risk_pairs``: optional tuple of ``(column_a,
      column_b)`` canonical pairs that are high-risk.
    - ``max_vif``: optional non-negative maximum variance
      inflation factor observed (only meaningful for numeric
      columns; categorical passes do not produce a VIF).
    - ``notes``: optional bounded human-readable note.
    """

    high_risk_threshold: _BoundedAbsoluteScore = Field(
        ...,
        description="Bounded absolute score threshold above which a pair is high-risk.",
    )
    high_risk_pair_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of high-risk pairs.",
    )
    high_risk_pairs: tuple[tuple[ColumnName, ColumnName], ...] = Field(
        default=(),
        description="Optional tuple of (column_a, column_b) canonical high-risk pairs.",
    )
    max_vif: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative maximum variance inflation factor observed.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _high_risk_pair_count_consistent(self) -> "MulticollinearityRiskSummary":
        if (
            self.high_risk_pair_count is not None
            and len(self.high_risk_pairs) != self.high_risk_pair_count
        ):
            raise ValueError(
                "MulticollinearityRiskSummary.high_risk_pair_count must equal "
                "the length of high_risk_pairs."
            )
        return self

    @model_validator(mode="after")
    def _high_risk_pairs_canonically_ordered(self) -> "MulticollinearityRiskSummary":
        for col_a, col_b in self.high_risk_pairs:
            if col_a == col_b:
                raise ValueError(
                    "MulticollinearityRiskSummary.high_risk_pairs must not contain self-pairs."
                )
            if col_a > col_b:
                raise ValueError(
                    f"MulticollinearityRiskSummary.high_risk_pairs must be in "
                    f"canonical (lexicographic) order; got ({col_a!r}, {col_b!r})."
                )
        return self


# ===========================================================================
# AssociationCheckReport
# ===========================================================================
class AssociationCheckReport(_AssociationsContractModel):
    """The typed output of stage 4.9 (diagnostic association checks).

    Per the interface map, this report is *diagnostic-only* and must
    not produce analytical findings on its own. A perfect
    association is allowed to trigger leakage re-checks downstream,
    but it does not, on its own, produce a conclusion.

    Fields:

    - ``dataset``: :class:`DatasetHandle` of the inspected dataset.
    - ``spec``: :class:`AssociationCheckSpec` actually used.
    - ``pairwise_summaries``: tuple of
      :class:`PairwiseAssociationSummary` (immutable). May be empty.
    - ``multicollinearity``: optional
      :class:`MulticollinearityRiskSummary` (only present when the
      spec requests it and the data supports it).
    - ``warnings``: tuple of :class:`AssociationWarning` (immutable).
    - ``issues``: common typed issue collection.
    - ``common_warnings``: common :class:`WarningRecord` collection.
    - ``perfect_association_count``: optional non-negative count of
      perfect associations detected (a discovery aid for reporting).
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the inspected dataset.",
    )
    spec: AssociationCheckSpec = Field(
        ...,
        description="AssociationCheckSpec actually used.",
    )
    pairwise_summaries: tuple[PairwiseAssociationSummary, ...] = Field(
        default=(),
        description="Tuple of PairwiseAssociationSummary (immutable).",
    )
    multicollinearity: MulticollinearityRiskSummary | None = Field(
        default=None,
        description="Optional MulticollinearityRiskSummary.",
    )
    warnings: tuple[AssociationWarning, ...] = Field(
        default=(),
        description="Tuple of AssociationWarning (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during diagnostics (immutable).",
    )
    common_warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during diagnostics (immutable).",
    )
    perfect_association_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of perfect associations detected.",
    )
    computed_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of report computation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _multicollinearity_consistent_with_spec(self) -> "AssociationCheckReport":
        if self.multicollinearity is not None and not self.spec.emit_multicollinearity_summary:
            raise ValueError(
                "AssociationCheckReport.multicollinearity is set but the "
                "spec.emit_multicollinearity_summary is False."
            )
        return self

    @model_validator(mode="after")
    def _pairwise_summaries_canonically_unique(self) -> "AssociationCheckReport":
        seen: set[tuple[str, str]] = set()
        for summary in self.pairwise_summaries:
            key = (summary.column_a, summary.column_b)
            if key in seen:
                raise ValueError(
                    f"AssociationCheckReport.pairwise_summaries has duplicate pair: {key!r}."
                )
            seen.add(key)
        return self

    @model_validator(mode="after")
    def _perfect_association_count_consistent(self) -> "AssociationCheckReport":
        if self.perfect_association_count is None:
            return self
        actual = sum(1 for s in self.pairwise_summaries if s.is_perfect is True)
        if self.perfect_association_count != actual:
            raise ValueError(
                "AssociationCheckReport.perfect_association_count must match "
                "the number of pairwise_summaries with is_perfect=True."
            )
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "AssociationCheckReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self
