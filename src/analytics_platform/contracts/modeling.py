"""Modeling contracts (Build Queue v2.1 Tasks 33-35).

Public contracts for the ``modeling`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Modeling contracts describe
the typed shapes that cross stages 4.18-4.23 of the interface map
(model spec validation, modeling data adapter, OLS fit, OLS result
extraction, fit metrics, diagnostics). They are dependency-light:
they import ``pydantic``, the standard library, and the shared
``common`` / ``datasets`` / ``schemas`` / ``semantics`` / ``features``
/ ``statistics`` contracts only. They never embed raw dataframes,
sample values, model objects, or backend objects.

Per the interface map:

- 4.18 (model spec validation): ``ModelSpec`` /
  ``OLSModelSpec`` / ``ModelSpecValidationReport``. Unsupported
  family, missing / constant target, no predictors, sample below
  minimum, predictive without holdout block; every block produces
  a typed reason.
- 4.19 (modeling data adapter): ``ModelFitRequest`` (with
  ``ExecutionLimitPolicy``); bounded private conversion; exceeds
  row / column limits blocks conversion with clear issue.
- 4.20 (OLS fit): ``ModelResult`` (typed summary only); no raw
  Statsmodels object in public output.
- 4.21 (OLS result extraction): ``CoefficientTable`` /
  ``ModelCoefficient`` / ``EffectEstimate`` / ``ConfidenceInterval``.
- 4.22 (model fit metrics): ``ModelMetricSet`` / ``MetricValue``.
- 4.23 (model diagnostics): ``ModelDiagnosticReport`` (fit /
  assumption / data / stability / interpretation-limit sections).

Scope:

- ``ModelType`` / ``ModelFamily`` / ``TargetType`` / ``ModelPurpose`` enums.
- ``OLSModelSpec`` / ``ModelSpec`` (Tasks 33-34).
- ``ModelSpecValidationReport`` (Task 33).
- ``ModelFitRequest`` (Tasks 34, 19 reuse).
- ``ModelCoefficient`` / ``CoefficientTable`` / ``EffectEstimate`` /
  ``ConfidenceInterval`` (Task 21, 35).
- ``ModelResult`` / ``ModelMetricSet`` (Tasks 35).
- ``ModelFitSummary`` / ``ModelAssumptionDiagnostics`` /
  ``ModelDataDiagnostics`` / ``ModelStabilityDiagnostics`` /
  ``ModelInterpretationLimit`` / ``AssumptionCheckResult`` /
  ``OverfittingCheckResult`` / ``ModelDiagnosticReport`` (Task 35).
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    MetricValue,
    ModelId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.execution import ExecutionLimitPolicy
from analytics_platform.contracts.features import FeatureBuildRequest
from analytics_platform.contracts.schemas import ColumnName
from analytics_platform.contracts.statistics import (
    ConfidenceInterval,
    EffectEstimate,
)

__all__ = [
    # Enums
    "ModelType",
    "ModelFamily",
    "TargetType",
    "ModelPurpose",
    # Spec
    "OLSModelSpec",
    "ModelSpec",
    "ModelSpecValidationReport",
    # Fit request
    "ModelFitRequest",
    # Result
    "ModelCoefficient",
    "CoefficientTable",
    "ModelResult",
    "ModelMetricSet",
    "ModelFitSummary",
    "ModelAssumptionDiagnostics",
    "ModelDataDiagnostics",
    "ModelStabilityDiagnostics",
    "ModelInterpretationLimit",
    "AssumptionCheckResult",
    "OverfittingCheckResult",
    "ModelDiagnosticReport",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ModelingContractModel(BaseModel):
    """Base configuration for modeling contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``). They never embed raw dataframes, sample
    values, model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for thresholds.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Enums
# ===========================================================================
class ModelType(str, Enum):
    """Catalogued model types.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``OLS`` is the only model type the v1.1 MVP
    supports; other types are reserved for future work.
    """

    OLS = "ols"
    LOGISTIC = "logistic"
    POISSON = "poisson"
    OTHER = "other"


class ModelFamily(str, Enum):
    """High-level model family classification.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``LINEAR`` covers OLS and variants;
    ``GLM`` is the parent for logistic / Poisson; ``OTHER`` is
    reserved for families the registry cannot classify.
    """

    LINEAR = "linear"
    GLM = "glm"
    OTHER = "other"


class TargetType(str, Enum):
    """Type of the model's target variable."""

    CONTINUOUS = "continuous"
    BINARY = "binary"
    COUNT = "count"
    OTHER = "other"


class ModelPurpose(str, Enum):
    """Why the model is being fit.

    Per the interface map (stage 4.14), predictive purpose requires
    a holdout unless overridden.
    """

    DESCRIPTIVE = "descriptive"
    PREDICTIVE = "predictive"
    INFERENTIAL = "inferential"
    OTHER = "other"


# ===========================================================================
# OLSModelSpec / ModelSpec
# ===========================================================================
class OLSModelSpec(_ModelingContractModel):
    """A typed OLS model specification.

    An ``OLSModelSpec`` pairs a target column with a tuple of
    predictor column names. The validator rejects empty
    predictors, ``include_intercept=False`` with an empty
    predictor list, and predictors equal to the target.

    Fields:

    - ``target_column``: :data:`ColumnName` of the target column.
    - ``predictor_columns``: tuple of :data:`ColumnName` of
      predictor columns. ``>= 1`` when ``include_intercept`` is
      ``True``; ``>= 1`` is also required when ``include_intercept``
      is ``False`` (regression with no intercept is allowed but
      needs at least one predictor).
    - ``include_intercept``: whether to fit an intercept term.
      Defaults to ``True``.
    - ``notes``: optional bounded human-readable note.
    """

    target_column: ColumnName = Field(
        ..., description="ColumnName of the target column."
    )
    predictor_columns: tuple[ColumnName, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of ColumnName of predictor columns (>= 1).",
    )
    include_intercept: bool = Field(
        default=True,
        description="Whether to fit an intercept term. Defaults to True.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _target_not_in_predictors(self) -> "OLSModelSpec":
        if self.target_column in self.predictor_columns:
            raise ValueError(
                "OLSModelSpec.target_column must not also appear in "
                "predictor_columns."
            )
        return self

    @model_validator(mode="after")
    def _predictor_columns_unique(self) -> "OLSModelSpec":
        seen: set[str] = set()
        for col in self.predictor_columns:
            if col in seen:
                raise ValueError(
                    f"OLSModelSpec.predictor_columns has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


class ModelSpec(_ModelingContractModel):
    """A typed top-level model specification.

    A ``ModelSpec`` is the canonical input to the model-spec
    validation stage (4.18). It pairs the requested ``ModelType`` /
    ``ModelFamily`` / ``TargetType`` / ``ModelPurpose`` with the
    type-specific spec (currently only ``OLSModelSpec``). When new
    model types are added, additional type-specific spec fields
    will be added here (or a discriminated union will be used).

    Fields:

    - ``model_id``: stable :data:`ModelId` for the model.
    - ``model_type``: :class:`ModelType`.
    - ``model_family``: :class:`ModelFamily`.
    - ``target_type``: :class:`TargetType`.
    - ``purpose``: :class:`ModelPurpose` (defaults to ``DESCRIPTIVE``).
    - ``ols_spec``: optional :class:`OLSModelSpec` (required when
      ``model_type == OLS``).
    - ``notes``: optional bounded human-readable note.
    """

    model_id: ModelId = Field(..., description="Stable ModelId for the model.")
    model_type: ModelType = Field(..., description="ModelType.")
    model_family: ModelFamily = Field(..., description="ModelFamily.")
    target_type: TargetType = Field(..., description="TargetType.")
    purpose: ModelPurpose = Field(
        default=ModelPurpose.DESCRIPTIVE,
        description="ModelPurpose. Defaults to DESCRIPTIVE.",
    )
    ols_spec: OLSModelSpec | None = Field(
        default=None,
        description="Optional OLSModelSpec. Required when model_type == OLS.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _ols_spec_consistent_with_model_type(self) -> "ModelSpec":
        if self.model_type is ModelType.OLS and self.ols_spec is None:
            raise ValueError(
                "ModelSpec with model_type=OLS must include an ols_spec."
            )
        if self.model_type is not ModelType.OLS and self.ols_spec is not None:
            raise ValueError(
                "ModelSpec.ols_spec is only valid when model_type=OLS."
            )
        return self


class ModelSpecValidationReport(_ModelingContractModel):
    """The typed outcome of model spec validation (stage 4.18).

    Per the interface map, unsupported family, missing / constant
    target, no predictors, sample below minimum, predictive
    without holdout block; every block produces a typed reason
    via ``block_reasons``.

    Fields:

    - ``spec``: the :class:`ModelSpec` that was validated.
    - ``passed``: whether the spec passed validation.
    - ``block_reasons``: tuple of bounded machine-readable
      ``(code, message)`` pairs. Populated when ``passed`` is
        ``False``.
    - ``warnings``: tuple of bounded machine-readable
      ``(code, message)`` pairs (advisory; do not block).
    - ``target_present``: whether the target column is present
      in the source dataset.
    - ``target_constant``: optional flag indicating the target
      column is constant.
    - ``sample_size``: optional non-negative count of samples
      available to the fit.
    - ``min_sample_size``: optional non-negative minimum sample
      size required for this model. ``sample_size < min_sample_size``
      blocks the fit.
    - ``holdout_required``: when ``True`` (predictive purpose),
      the fit requires a holdout.
    - ``holdout_present``: optional flag indicating whether a
      holdout is configured.
    - ``issues`` / ``warnings_records``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    spec: ModelSpec = Field(..., description="ModelSpec that was validated.")
    passed: bool = Field(..., description="Whether the spec passed validation.")
    block_reasons: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Tuple of (code, message) block reasons.",
    )
    warnings: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Tuple of (code, message) advisory warnings.",
    )
    target_present: bool | None = Field(
        default=None,
        description="Optional flag indicating the target column is present.",
    )
    target_constant: bool | None = Field(
        default=None,
        description="Optional flag indicating the target column is constant.",
    )
    sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of samples available.",
    )
    min_sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative minimum sample size required.",
    )
    holdout_required: bool | None = Field(
        default=None,
        description="Optional flag indicating the fit requires a holdout.",
    )
    holdout_present: bool | None = Field(
        default=None,
        description="Optional flag indicating a holdout is configured.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings_records: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None

    @model_validator(mode="after")
    def _passed_consistent(self) -> "ModelSpecValidationReport":
        if self.passed and self.block_reasons:
            raise ValueError(
                "ModelSpecValidationReport with passed=True must not include block_reasons."
            )
        if not self.passed and not self.block_reasons:
            raise ValueError(
                "ModelSpecValidationReport with passed=False must include at least one block_reason."
            )
        if self.passed and self.target_constant is True:
            raise ValueError(
                "ModelSpecValidationReport with passed=True must not have target_constant=True."
            )
        return self

    @model_validator(mode="after")
    def _block_reasons_codes_unique(self) -> "ModelSpecValidationReport":
        seen: set[str] = set()
        for code, _message in self.block_reasons:
            if not code:
                raise ValueError(
                    "ModelSpecValidationReport.block_reasons codes must be non-empty."
                )
            if code in seen:
                raise ValueError(
                    f"ModelSpecValidationReport.block_reasons has duplicate code: {code!r}."
                )
            seen.add(code)
        return self

    @model_validator(mode="after")
    def _sample_size_consistent(self) -> "ModelSpecValidationReport":
        if (
            self.sample_size is not None
            and self.min_sample_size is not None
            and self.sample_size < self.min_sample_size
        ):
            raise ValueError(
                "ModelSpecValidationReport.sample_size must be >= min_sample_size "
                "when both are set."
            )
        return self


# ===========================================================================
# ModelFitRequest
# ===========================================================================
class ModelFitRequest(_ModelingContractModel):
    """A typed request to fit a model (stage 4.20 input).

    A ``ModelFitRequest`` pairs the validated
    ``ModelSpecValidationReport`` with a :class:`FeatureBuildRequest`
    and the :class:`ExecutionLimitPolicy` to apply. It must not
    reference raw dataframes, sample values, or backend objects.

    Fields:

    - ``validation_report``: :class:`ModelSpecValidationReport`
      that approves the fit.
    - ``feature_build``: :class:`FeatureBuildRequest` that
      produced the model-ready matrix.
    - ``execution_limits``: :class:`ExecutionLimitPolicy` to
      apply during the bounded private conversion (4.19).
    - ``explicit_override``: when ``True``, allows the fit even
      when the validation report is not ``passed``. Defaults to
      ``False``.
    - ``override_reason``: optional bounded reason. Required
      when ``explicit_override`` is ``True``.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    validation_report: ModelSpecValidationReport = Field(
        ...,
        description="ModelSpecValidationReport that approves the fit.",
    )
    feature_build: FeatureBuildRequest = Field(
        ...,
        description="FeatureBuildRequest that produced the model-ready matrix.",
    )
    execution_limits: ExecutionLimitPolicy = Field(
        ...,
        description="ExecutionLimitPolicy to apply during the bounded private conversion.",
    )
    explicit_override: bool = Field(
        default=False,
        description="When True, allows the fit even when the validation report is not passed.",
    )
    override_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded reason. Required when explicit_override is True.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _override_consistent(self) -> "ModelFitRequest":
        if self.explicit_override and not self.override_reason:
            raise ValueError(
                "ModelFitRequest with explicit_override=True must include a non-empty override_reason."
            )
        return self

    @model_validator(mode="after")
    def _approved_or_overridden(self) -> "ModelFitRequest":
        if self.validation_report.passed:
            return self
        if self.explicit_override:
            return self
        raise ValueError(
            "ModelFitRequest requires a passed ModelSpecValidationReport, "
            "or an explicit override with a non-empty override_reason."
        )


# ===========================================================================
# ModelCoefficient / CoefficientTable / ModelResult
# ===========================================================================
class ModelCoefficient(_ModelingContractModel):
    """A single fitted-model coefficient (Task 21 / 35 output).

    Fields:

    - ``name``: stable name of the coefficient (e.g. a predictor
      column name or ``"intercept"``).
    - ``estimate``: real-number point estimate.
    - ``standard_error``: optional non-negative standard error.
    - ``t_statistic`` / ``p_value``: optional test statistics.
    - ``confidence_interval``: optional
      :class:`analytics_platform.contracts.statistics.ConfidenceInterval`.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable name of the coefficient.",
    )
    estimate: float = Field(..., description="Real-number point estimate.")
    standard_error: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative standard error.",
    )
    t_statistic: float | None = Field(
        default=None,
        description="Optional t-statistic.",
    )
    p_value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional bounded p-value in [0.0, 1.0].",
    )
    confidence_interval: ConfidenceInterval | None = Field(
        default=None,
        description="Optional ConfidenceInterval.",
    )


class CoefficientTable(_ModelingContractModel):
    """A bounded coefficient table (Task 21 / 35 output).

    Fields:

    - ``coefficients``: tuple of :class:`ModelCoefficient`. Names
      are unique. The order is significant; callers should treat
      the tuple as an ordered list.
    - ``notes``: optional bounded human-readable note.
    """

    coefficients: tuple[ModelCoefficient, ...] = Field(
        default=(),
        description="Tuple of ModelCoefficient (immutable, ordered).",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _coefficient_names_unique(self) -> "CoefficientTable":
        seen: set[str] = set()
        for c in self.coefficients:
            if c.name in seen:
                raise ValueError(
                    f"CoefficientTable has duplicate coefficient name: {c.name!r}."
                )
            seen.add(c.name)
        return self


class ModelMetricSet(_ModelingContractModel):
    """A typed set of model fit metrics (Task 22 / 35 output).

    Fields:

    - ``metrics``: tuple of :class:`MetricValue`. Names are
      unique.
    - ``scope``: optional bounded scope label (``"train"`` /
      ``"holdout"`` / ``"test"``).
    - ``notes``: optional bounded human-readable note.
    """

    metrics: tuple[MetricValue, ...] = Field(
        default=(),
        description="Tuple of MetricValue (immutable).",
    )
    scope: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded scope label (e.g. 'train' / 'holdout' / 'test').",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _metric_names_unique(self) -> "ModelMetricSet":
        seen: set[str] = set()
        for m in self.metrics:
            if m.name in seen:
                raise ValueError(
                    f"ModelMetricSet has duplicate metric name: {m.name!r}."
                )
            seen.add(m.name)
        return self


class ModelFitSummary(_ModelingContractModel):
    """A typed fit summary (Task 22 / 35 output).

    Fields:

    - ``r_squared`` / ``adjusted_r_squared``: optional real-number
      R^2 and adjusted R^2.
    - ``f_statistic`` / ``f_p_value``: optional F-statistic and
      associated p-value.
    - ``residual_std_error``: optional non-negative residual
      standard error.
    - ``degrees_of_freedom_residual``: optional non-negative
      residual degrees of freedom.
    - ``aic`` / ``bic``: optional information criteria.
    """

    r_squared: float | None = Field(
        default=None, description="Optional real-number R^2."
    )
    adjusted_r_squared: float | None = Field(
        default=None, description="Optional real-number adjusted R^2."
    )
    f_statistic: float | None = Field(
        default=None, description="Optional F-statistic."
    )
    f_p_value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional bounded p-value in [0.0, 1.0].",
    )
    residual_std_error: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative residual standard error.",
    )
    degrees_of_freedom_residual: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative residual degrees of freedom.",
    )
    aic: float | None = Field(
        default=None, description="Optional Akaike Information Criterion."
    )
    bic: float | None = Field(
        default=None, description="Optional Bayesian Information Criterion."
    )


class ModelResult(_ModelingContractModel):
    """The typed output of a model fit (Task 20 / 35).

    Per the interface map, ``ModelResult`` is a typed summary only;
    it must never embed a raw Statsmodels object. All fit output is
    expressed as typed coefficients, fit summary, and metric sets.

    Fields:

    - ``model_id``: :data:`ModelId` of the model that was fit.
    - ``coefficient_table``: :class:`CoefficientTable` of fitted
      coefficients.
    - ``fit_summary``: optional :class:`ModelFitSummary`.
    - ``metric_sets``: tuple of :class:`ModelMetricSet`. May
      contain a single ``"train"`` set or multiple ``"train"`` /
      ``"holdout"`` / ``"test"`` sets.
    - ``fit_at``: optional timezone-aware timestamp of the fit.
    - ``sample_size``: optional non-negative count of samples
      used.
    - ``degrees_of_freedom_model``: optional non-negative model
      degrees of freedom.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    model_id: ModelId = Field(
        ..., description="ModelId of the model that was fit."
    )
    coefficient_table: CoefficientTable = Field(
        ..., description="CoefficientTable of fitted coefficients."
    )
    fit_summary: ModelFitSummary | None = Field(
        default=None, description="Optional ModelFitSummary."
    )
    metric_sets: tuple[ModelMetricSet, ...] = Field(
        default=(),
        description="Tuple of ModelMetricSet (immutable).",
    )
    fit_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of the fit.",
    )
    sample_size: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of samples used.",
    )
    degrees_of_freedom_model: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative model degrees of freedom.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _metric_set_scopes_unique(self) -> "ModelResult":
        seen: set[str] = set()
        for ms in self.metric_sets:
            if ms.scope is None:
                continue
            if ms.scope in seen:
                raise ValueError(
                    f"ModelResult.metric_sets has duplicate scope: {ms.scope!r}."
                )
            seen.add(ms.scope)
        return self

    @model_validator(mode="after")
    def _fit_at_is_timezone_aware(self) -> "ModelResult":
        if self.fit_at is not None and self.fit_at.tzinfo is None:
            object.__setattr__(
                self, "fit_at", self.fit_at.replace(tzinfo=timezone.utc)
            )
        return self


# ===========================================================================
# Model diagnostics
# ===========================================================================
class AssumptionCheckResult(_ModelingContractModel):
    """A single assumption-check result (Task 35).

    Fields:

    - ``name``: stable name of the assumption (``"normality_of_residuals"``,
      ``"homoscedasticity"``, etc.).
    - ``passed``: whether the assumption check passed.
    - ``statistic``: optional real-number test statistic.
    - ``p_value``: optional bounded p-value in ``[0.0, 1.0]``.
    - ``severity``: :class:`Severity` of the result.
    - ``message``: human-readable message.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable name of the assumption.",
    )
    passed: bool = Field(..., description="Whether the assumption check passed.")
    statistic: float | None = Field(
        default=None, description="Optional real-number test statistic."
    )
    p_value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional bounded p-value in [0.0, 1.0].",
    )
    severity: Severity = Field(..., description="Severity of the result.")
    message: str = Field(..., min_length=1, description="Human-readable message.")


class ModelAssumptionDiagnostics(_ModelingContractModel):
    """The assumption-diagnostics section of a model diagnostic report.

    Fields:

    - ``checks``: tuple of :class:`AssumptionCheckResult`. Names
      are unique.
    - ``any_severe_violation``: when ``True``, at least one check
      had severity ``ERROR`` or ``CRITICAL`` and ``passed=False``.
      Per the interface map, severe assumption violations
      downgrade coefficient-level interpretation.
    """

    checks: tuple[AssumptionCheckResult, ...] = Field(
        default=(),
        description="Tuple of AssumptionCheckResult (immutable).",
    )
    any_severe_violation: bool = Field(
        default=False,
        description=(
            "When True, at least one check had ERROR/CRITICAL severity and "
            "did not pass."
        ),
    )

    @model_validator(mode="after")
    def _check_names_unique(self) -> "ModelAssumptionDiagnostics":
        seen: set[str] = set()
        for c in self.checks:
            if c.name in seen:
                raise ValueError(
                    f"ModelAssumptionDiagnostics has duplicate check name: {c.name!r}."
                )
            seen.add(c.name)
        return self

    @model_validator(mode="after")
    def _severe_violation_consistent(self) -> "ModelAssumptionDiagnostics":
        computed = any(
            (not c.passed)
            and c.severity in (Severity.ERROR, Severity.CRITICAL)
            for c in self.checks
        )
        if self.any_severe_violation and not computed:
            raise ValueError(
                "ModelAssumptionDiagnostics.any_severe_violation=True "
                "requires at least one non-passed ERROR/CRITICAL check."
            )
        if computed and not self.any_severe_violation:
            raise ValueError(
                "ModelAssumptionDiagnostics with a non-passed ERROR/CRITICAL "
                "check must have any_severe_violation=True."
            )
        return self


class ModelDataDiagnostics(_ModelingContractModel):
    """The data-diagnostics section (multicollinearity, etc.).

    Fields:

    - ``max_vif``: optional non-negative maximum VIF observed.
    - ``high_vif_predictors``: tuple of :data:`ColumnName` of
      predictors with VIF above the documented threshold. Names
      are unique.
    - ``influential_observations``: optional non-negative count
      of influential observations (e.g. high Cook's distance).
    - ``notes``: optional bounded human-readable note.
    """

    max_vif: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional non-negative maximum VIF observed.",
    )
    high_vif_predictors: tuple[ColumnName, ...] = Field(
        default=(),
        description="Optional tuple of ColumnName of predictors with VIF above threshold.",
    )
    influential_observations: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of influential observations.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _high_vif_unique(self) -> "ModelDataDiagnostics":
        seen: set[str] = set()
        for col in self.high_vif_predictors:
            if col in seen:
                raise ValueError(
                    f"ModelDataDiagnostics.high_vif_predictors has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


class OverfittingCheckResult(_ModelingContractModel):
    """A typed overfitting check result.

    Fields:

    - ``check_type``: bounded label (``"train_test_r2_gap"``,
      ``"holdout_disabled"``, etc.).
    - ``passed``: whether the overfitting check passed.
    - ``gap_value``: optional real-number gap value (e.g. R^2
      train - R^2 holdout).
    - ``severity``: :class:`Severity` of the result.
    - ``message``: human-readable message.
    """

    check_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Bounded label for the overfitting check.",
    )
    passed: bool = Field(..., description="Whether the overfitting check passed.")
    gap_value: float | None = Field(
        default=None,
        description="Optional real-number gap value.",
    )
    severity: Severity = Field(..., description="Severity of the result.")
    message: str = Field(..., min_length=1, description="Human-readable message.")


class ModelStabilityDiagnostics(_ModelingContractModel):
    """The stability-diagnostics section (overfitting, robustness).

    Fields:

    - ``overfitting_checks``: tuple of
      :class:`OverfittingCheckResult`. ``check_type`` values are
      unique.
    - ``any_severe_overfitting``: when ``True``, at least one
      overfitting check had severity ``ERROR`` or ``CRITICAL`` and
      ``passed=False``.
    - ``notes``: optional bounded human-readable note.
    """

    overfitting_checks: tuple[OverfittingCheckResult, ...] = Field(
        default=(),
        description="Tuple of OverfittingCheckResult (immutable).",
    )
    any_severe_overfitting: bool = Field(
        default=False,
        description="When True, at least one overfitting check failed with ERROR/CRITICAL severity.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _overfitting_check_types_unique(self) -> "ModelStabilityDiagnostics":
        seen: set[str] = set()
        for c in self.overfitting_checks:
            if c.check_type in seen:
                raise ValueError(
                    f"ModelStabilityDiagnostics has duplicate overfitting_check type: {c.check_type!r}."
                )
            seen.add(c.check_type)
        return self

    @model_validator(mode="after")
    def _severe_overfitting_consistent(self) -> "ModelStabilityDiagnostics":
        computed = any(
            (not c.passed)
            and c.severity in (Severity.ERROR, Severity.CRITICAL)
            for c in self.overfitting_checks
        )
        if self.any_severe_overfitting and not computed:
            raise ValueError(
                "ModelStabilityDiagnostics.any_severe_overfitting=True requires "
                "at least one non-passed ERROR/CRITICAL check."
            )
        if computed and not self.any_severe_overfitting:
            raise ValueError(
                "ModelStabilityDiagnostics with a non-passed ERROR/CRITICAL "
                "check must have any_severe_overfitting=True."
            )
        return self


class ModelInterpretationLimit(_ModelingContractModel):
    """A typed interpretation-limit finding.

    Per the interface map, severe assumption violations downgrade
    coefficient-level interpretation. An interpretation limit
    records a single limitation that downstream consumers must
    surface to the user.

    Fields:

    - ``code``: stable machine-readable code.
    - ``severity``: :class:`Severity`.
    - ``message``: human-readable message.
    - ``downgrades_coefficient_interpretation``: when ``True``,
      the limit causes coefficient-level interpretation to be
      downgraded (e.g. from ``DESCRIPTIVE`` to ``EXPLORATORY``).
    - ``related_check``: optional name of the related
      ``AssumptionCheckResult`` or ``OverfittingCheckResult``.
    """

    code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable code.",
    )
    severity: Severity = Field(..., description="Severity.")
    message: str = Field(..., min_length=1, description="Human-readable message.")
    downgrades_coefficient_interpretation: bool = Field(
        default=False,
        description="When True, the limit causes coefficient-level interpretation to be downgraded.",
    )
    related_check: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional name of the related assumption or overfitting check.",
    )


class ModelDiagnosticReport(_ModelingContractModel):
    """The typed output of stage 4.23 (model diagnostics).

    Per the interface map, a model diagnostic report has fit,
    assumption, data, stability, and interpretation-limit sections.
    Severe assumption violations downgrade coefficient-level
    interpretation; the ``interpretation_limits`` section makes
    that visible to consumers.

    Fields:

    - ``model_id``: :data:`ModelId` of the model that was
      diagnosed.
    - ``fit_summary``: optional :class:`ModelFitSummary`.
    - ``assumptions``: :class:`ModelAssumptionDiagnostics`.
    - ``data_diagnostics``: :class:`ModelDataDiagnostics`.
    - ``stability``: :class:`ModelStabilityDiagnostics`.
    - ``interpretation_limits``: tuple of
      :class:`ModelInterpretationLimit`. Codes are unique.
    - ``issues`` / ``warnings_records``: common typed collections.
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    model_id: ModelId = Field(
        ..., description="ModelId of the model that was diagnosed."
    )
    fit_summary: ModelFitSummary | None = Field(
        default=None, description="Optional ModelFitSummary."
    )
    assumptions: ModelAssumptionDiagnostics = Field(
        ..., description="ModelAssumptionDiagnostics."
    )
    data_diagnostics: ModelDataDiagnostics = Field(
        ..., description="ModelDataDiagnostics."
    )
    stability: ModelStabilityDiagnostics = Field(
        ..., description="ModelStabilityDiagnostics."
    )
    interpretation_limits: tuple[ModelInterpretationLimit, ...] = Field(
        default=(),
        description="Tuple of ModelInterpretationLimit (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during diagnostics (immutable).",
    )
    warnings_records: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during diagnostics (immutable).",
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
    def _interpretation_limit_codes_unique(self) -> "ModelDiagnosticReport":
        seen: set[str] = set()
        for lim in self.interpretation_limits:
            if lim.code in seen:
                raise ValueError(
                    f"ModelDiagnosticReport.interpretation_limits has duplicate code: {lim.code!r}."
                )
            seen.add(lim.code)
        return self

    @model_validator(mode="after")
    def _downgrade_consistent_with_assumptions(self) -> "ModelDiagnosticReport":
        for lim in self.interpretation_limits:
            if (
                lim.downgrades_coefficient_interpretation
                and not self.assumptions.any_severe_violation
            ):
                raise ValueError(
                    "ModelDiagnosticReport.interpretation_limits entry with "
                    "downgrades_coefficient_interpretation=True requires "
                    "assumptions.any_severe_violation=True."
                )
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "ModelDiagnosticReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self
