"""Statistics contracts (Build Queue v2.1 Task 32).

Public contracts for the ``statistics`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Statistics contracts
describe the typed shapes that cross the statistics stages of the
interface map (stage 4.24: multiple-testing correction). They are
dependency-light: they import ``pydantic``, the standard library,
and the shared ``common`` / ``schemas`` / ``semantics`` / ``features``
contracts only. They never embed raw dataframes, sample values,
model objects, or backend objects.

Per the interface map (stage 4.24), the statistics stage operates on
declared test families and reports a
:class:`MultipleTestingCorrectionReport` per family. Unadjusted
p-values are not discovery guarantees; a skipped correction is
disclosed in the report.

Scope:

- ``MultipleTestingCorrectionMethod`` enum.
- ``TestFamily`` enum.
- ``EffectEstimate`` / ``ConfidenceInterval`` models.
- ``PValueAdjustmentResult`` per-p-value row.
- ``StatisticalTestResult`` typed output.
- ``MultipleTestingCorrectionReport`` typed report.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from analytics_platform.contracts.common import (
    Issue,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)

__all__ = [
    "MultipleTestingCorrectionMethod",
    "TestFamily",
    "EffectEstimate",
    "ConfidenceInterval",
    "PValueAdjustmentResult",
    "StatisticalTestResult",
    "MultipleTestingCorrectionReport",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _StatisticsContractModel(BaseModel):
    """Base configuration for statistics contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``). They never embed raw dataframes, sample
    values, model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded p-value in [0.0, 1.0] (inclusive at both ends; 0.0 is a
# perfectly valid p-value, 1.0 is the upper bound).
_BoundedPValue = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Enums
# ===========================================================================
class MultipleTestingCorrectionMethod(str, Enum):
    """Catalogued multiple-testing correction methods.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The enum is documentation-level; new methods
    may be added in later tasks.
    """

    BONFERRONI = "bonferroni"
    HOLM = "holm"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    BENJAMINI_YEKUTIELI = "benjamini_yekutieli"
    SIDAK = "sidak"
    NONE = "none"
    UNKNOWN = "unknown"


class TestFamily(str, Enum):
    """Catalogued test families for multiple-testing correction.

    Per the interface map (stage 4.24), correction is applied within
    a declared family; cross-family pooling is not allowed. ``OTHER``
    is reserved for families the stage cannot classify.
    """

    COEFFICIENT = "coefficient"
    ASSOCIATION = "association"
    GROUP_DIFFERENCE = "group_difference"
    OTHER = "other"

    # Opt out of pytest's test-class collection: this is an Enum, not
    # a pytest test class. Without this, pytest warns that it "cannot
    # collect test class 'TestFamily' because it has a __init__
    # constructor".
    __test__ = False


# ===========================================================================
# EffectEstimate / ConfidenceInterval
# ===========================================================================
class ConfidenceInterval(_StatisticsContractModel):
    """A bounded confidence interval for a single effect estimate.

    Fields:

    - ``lower`` / ``upper``: real-number bounds. ``upper >= lower`` when
      both are set.
    - ``confidence_level``: optional non-negative bounded level in
      ``[0.0, 1.0]`` (e.g. ``0.95`` for a 95% CI).
    - ``method``: optional bounded method label (``"wald"`` /
      ``"bootstrap"`` / etc.).
    """

    lower: float | None = Field(
        default=None,
        description="Optional real-number lower bound.",
    )
    upper: float | None = Field(
        default=None,
        description="Optional real-number upper bound.",
    )
    confidence_level: Annotated[float, Field(ge=0.0, le=1.0)] | None = Field(
        default=None,
        description="Optional non-negative bounded confidence level in [0.0, 1.0].",
    )
    method: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded method label.",
    )

    @model_validator(mode="after")
    def _lower_le_upper(self) -> "ConfidenceInterval":
        if (
            self.lower is not None
            and self.upper is not None
            and self.upper < self.lower
        ):
            raise ValueError(
                "ConfidenceInterval.upper must be >= lower."
            )
        return self


class EffectEstimate(_StatisticsContractModel):
    """A typed effect estimate with optional confidence interval.

    Fields:

    - ``point``: real-number point estimate.
    - ``standard_error``: optional non-negative standard error.
    - ``confidence_interval``: optional :class:`ConfidenceInterval`.
    - ``units``: optional bounded units label (``"USD"`` /
      ``"log_odds"`` / etc.).
    """

    point: float = Field(..., description="Real-number point estimate.")
    standard_error: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative standard error.",
    )
    confidence_interval: ConfidenceInterval | None = Field(
        default=None,
        description="Optional ConfidenceInterval.",
    )
    units: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded units label.",
    )


# ===========================================================================
# PValueAdjustmentResult
# ===========================================================================
class PValueAdjustmentResult(_StatisticsContractModel):
    """A per-hypothesis p-value adjustment result.

    A :class:`PValueAdjustmentResult` records the original p-value,
    the adjusted p-value, and the optional rank. It is the row
    element of a :class:`MultipleTestingCorrectionReport`.

    Fields:

    - ``hypothesis_id``: stable identifier of the hypothesis this
      row refers to (e.g. a coefficient name).
    - ``raw_p_value``: bounded p-value in ``[0.0, 1.0]``.
    - ``adjusted_p_value``: bounded p-value in ``[0.0, 1.0]``.
    - ``rank``: optional non-negative rank (1 = most significant).
      ``None`` when the method does not produce a rank.
    - ``rejected``: optional flag indicating the hypothesis is
      rejected at the family-level significance threshold.
    - ``method``: optional bounded method label actually used
      (overrides the family-level method when set).
    """

    hypothesis_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier of the hypothesis this row refers to.",
    )
    raw_p_value: _BoundedPValue = Field(
        ...,
        description="Bounded raw p-value in [0.0, 1.0].",
    )
    adjusted_p_value: _BoundedPValue = Field(
        ...,
        description="Bounded adjusted p-value in [0.0, 1.0].",
    )
    rank: int | None = Field(
        default=None,
        ge=1,
        description="Optional non-negative rank (1 = most significant).",
    )
    rejected: bool | None = Field(
        default=None,
        description="Optional flag indicating the hypothesis is rejected at the family threshold.",
    )
    method: MultipleTestingCorrectionMethod | None = Field(
        default=None,
        description="Optional correction method actually used for this row.",
    )


# ===========================================================================
# StatisticalTestResult
# ===========================================================================
class StatisticalTestResult(_StatisticsContractModel):
    """A typed statistical test result for a single hypothesis.

    Fields:

    - ``test_id``: stable identifier of the test (e.g. a coefficient
      name).
    - ``family``: :class:`TestFamily` the test belongs to.
    - ``statistic``: real-number test statistic.
    - ``p_value``: bounded p-value in ``[0.0, 1.0]``.
    - ``effect``: optional :class:`EffectEstimate`.
    - ``degrees_of_freedom``: optional non-negative degrees of freedom.
    - ``method``: optional bounded method label.
    - ``notes``: optional bounded human-readable note.
    """

    test_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier of the test.",
    )
    family: TestFamily = Field(
        ..., description="TestFamily the test belongs to."
    )
    statistic: float = Field(..., description="Real-number test statistic.")
    p_value: _BoundedPValue = Field(
        ...,
        description="Bounded p-value in [0.0, 1.0].",
    )
    effect: EffectEstimate | None = Field(
        default=None,
        description="Optional EffectEstimate.",
    )
    degrees_of_freedom: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative degrees of freedom.",
    )
    method: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded method label.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


# ===========================================================================
# MultipleTestingCorrectionReport
# ===========================================================================
class MultipleTestingCorrectionReport(_StatisticsContractModel):
    """A typed multiple-testing correction report (stage 4.24).

    Per the interface map, the statistics stage operates on a
    declared test family and reports a per-hypothesis
    :class:`PValueAdjustmentResult` table. Unadjusted p-values are
    not discovery guarantees; a skipped correction is disclosed via
    the ``skipped`` flag and the bounded ``correction_method``.

    Fields:

    - ``family``: :class:`TestFamily` the correction was applied to.
    - ``correction_method``: :class:`MultipleTestingCorrectionMethod`.
    - ``alpha``: bounded family-level significance threshold in
      ``[0.0, 1.0]``.
    - ``n_tests``: optional non-negative count of tests in the
      family.
    - ``n_rejected``: optional non-negative count of rejected tests.
    - ``adjustments``: tuple of :class:`PValueAdjustmentResult`
      (immutable; may be empty when ``skipped`` is ``True``).
    - ``skipped``: ``True`` when the correction was not applied.
    - ``skip_reason``: optional bounded reason (populated when
      ``skipped`` is ``True``).
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    family: TestFamily = Field(
        ...,
        description="TestFamily the correction was applied to.",
    )
    correction_method: MultipleTestingCorrectionMethod = Field(
        ...,
        description="MultipleTestingCorrectionMethod used.",
    )
    alpha: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ...,
        description="Bounded family-level significance threshold in [0.0, 1.0].",
    )
    n_tests: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of tests in the family.",
    )
    n_rejected: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of rejected tests.",
    )
    adjustments: tuple[PValueAdjustmentResult, ...] = Field(
        default=(),
        description="Tuple of PValueAdjustmentResult (immutable).",
    )
    skipped: bool = Field(
        default=False,
        description="True when the correction was not applied.",
    )
    skip_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded reason. Populated when skipped is True.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during correction (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during correction (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _skipped_consistent(self) -> "MultipleTestingCorrectionReport":
        if self.skipped and not self.skip_reason:
            raise ValueError(
                "MultipleTestingCorrectionReport with skipped=True must "
                "include a non-empty skip_reason."
            )
        if not self.skipped and self.skip_reason:
            raise ValueError(
                "MultipleTestingCorrectionReport with skipped=False must "
                "not include a skip_reason."
            )
        if (
            self.correction_method is MultipleTestingCorrectionMethod.NONE
            and not self.skipped
        ):
            raise ValueError(
                "MultipleTestingCorrectionReport with correction_method=NONE "
                "must have skipped=True."
            )
        return self

    @model_validator(mode="after")
    def _n_rejected_does_not_exceed_n_tests(self) -> "MultipleTestingCorrectionReport":
        if (
            self.n_rejected is not None
            and self.n_tests is not None
            and self.n_rejected > self.n_tests
        ):
            raise ValueError(
                "MultipleTestingCorrectionReport.n_rejected must not exceed n_tests."
            )
        return self

    @model_validator(mode="after")
    def _hypothesis_ids_unique(self) -> "MultipleTestingCorrectionReport":
        seen: set[str] = set()
        for adj in self.adjustments:
            if adj.hypothesis_id in seen:
                raise ValueError(
                    f"MultipleTestingCorrectionReport.adjustments has duplicate "
                    f"hypothesis_id: {adj.hypothesis_id!r}."
                )
            seen.add(adj.hypothesis_id)
        return self
