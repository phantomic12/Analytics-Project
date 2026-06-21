"""Feature spec, transformation, matrix, and leakage contracts.

Build Queue v2.1 Tasks 28-31. Public contracts for the ``features``
contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Feature contracts describe
the typed shapes that cross stages 4.13 (feature spec resolution),
4.14 (split planning), 4.15 (transformation planning), 4.16 (matrix
build), and 4.17 (leakage checks) of the interface map.

Per the interface map:

- 4.13: feature spec resolution produces a
  :class:`FeatureEligibilityReport`; missing target or invalid
  feature refs block feature build.
- 4.14: split planning produces split refs and a ``requires_holdout``
  flag; predictive purpose requires a holdout unless overridden.
- 4.15: transformation planning produces a
  :class:`FeatureTransformationPlan` and a
  :class:`PreprocessingFitScope`; fitted transforms must declare
  train-only fit scope.
- 4.16: matrix build produces a :class:`FeatureMatrixResult` and
  :class:`FeatureMatrixRef` plus
  :class:`RowsExcludedReport` / :class:`ColumnsExcludedReport`; no
  raw matrix object in the public result.
- 4.17: leakage checks produce a :class:`LeakageCheckReport` and
  :class:`LeakageRisk`; target-as-feature, post-outcome predictors,
  and train/test contamination block by default.

Contracts are dependency-light: they import ``pydantic``, the
standard library, and the shared ``common`` / ``datasets`` /
``schemas`` / ``semantics`` contracts only. They never embed raw
dataframes, sample values, model objects, or backend objects.

Scope:

- ``TargetSpec`` / ``FeatureSpec`` / ``SplitSpec`` (Task 28).
- ``MissingValueStrategy`` / ``EncodingStrategy`` /
  ``ScalingStrategy`` / ``SplitStrategy`` /
  ``PreprocessingFitScope`` (Tasks 28-29).
- ``FeatureBuildRequest`` (Tasks 28-29).
- ``FeatureEligibilityReport`` (Task 28).
- ``FeatureTransformationPlan`` / ``FeatureTransformationReport``
  (Task 29).
- ``FeatureMatrixRef`` / ``FeatureMatrixResult`` /
  ``RowsExcludedReport`` / ``ColumnsExcludedReport`` /
  ``FeatureExclusionReason`` (Task 30).
- ``LeakageCheckRequest`` / ``LeakageCheckReport`` /
  ``LeakageRisk`` / ``LeakageRiskType`` (Task 31).
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
    ArtifactId,
    DatasetId,
    ExecutionStatus,
    Issue,
    LineageId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import ColumnName

__all__ = [
    # Task 28
    "TargetSpec",
    "TargetTask",
    "FeatureSpec",
    "ColumnRole",
    "SplitStrategy",
    "SplitSpec",
    "FeatureBuildRequest",
    "FeatureEligibilityReport",
    # Task 29
    "MissingValueStrategy",
    "EncodingStrategy",
    "ScalingStrategy",
    "PreprocessingFitScope",
    "FeatureTransformationPlan",
    "FeatureTransformationReport",
    # Task 30
    "FeatureMatrixRef",
    "FeatureMatrixResult",
    "RowsExcludedReport",
    "ColumnsExcludedReport",
    "FeatureExclusionReason",
    # Task 31
    "LeakageCheckRequest",
    "LeakageCheckReport",
    "LeakageRisk",
    "LeakageRiskType",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _FeaturesContractModel(BaseModel):
    """Base configuration for feature contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so the public surface stays explicit and stable.
    There is deliberately no field for raw dataframes, sample values,
    model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for holdout / split fractions.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Enums shared across the family
# ===========================================================================
class ColumnRole(str, Enum):
    """Pipeline role for a column. Re-exported for convenience.

    The full role enum lives in ``analytics_platform.contracts.semantics``;
    re-declared here so :class:`FeatureSpec` does not need to import
    the semantics family (which would create a circular import).
    The values are identical to the semantics enum.
    """

    TARGET = "target"
    FEATURE = "feature"
    EXCLUSION = "exclusion"
    GROUP_KEY = "group_key"
    WEIGHT = "weight"
    TIME_INDEX = "time_index"
    NONE = "none"


class TargetTask(str, Enum):
    """Catalogued target task types."""

    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    MULTICLASS = "multiclass"


class SplitStrategy(str, Enum):
    """Catalogued data-split strategies."""

    RANDOM = "random"
    STRATIFIED = "stratified"
    TIME = "time"
    GROUP = "group"
    NONE = "none"


class MissingValueStrategy(str, Enum):
    """Catalogued missing-value imputation strategies."""

    DROP_ROW = "drop_row"
    DROP_COLUMN = "drop_column"
    IMPUTE_MEAN = "impute_mean"
    IMPUTE_MEDIAN = "impute_median"
    IMPUTE_MOST_FREQUENT = "impute_most_frequent"
    IMPUTE_CONSTANT = "impute_constant"
    ADD_MISSING_INDICATOR = "add_missing_indicator"
    NONE = "none"


class EncodingStrategy(str, Enum):
    """Catalogued categorical-encoding strategies."""

    ONE_HOT = "one_hot"
    ORDINAL = "ordinal"
    TARGET = "target"
    HASH = "hash"
    NONE = "none"


class ScalingStrategy(str, Enum):
    """Catalogued numeric-scaling strategies."""

    STANDARD = "standard"
    MIN_MAX = "min_max"
    ROBUST = "robust"
    NONE = "none"


class PreprocessingFitScope(str, Enum):
    """Where preprocessing fits are allowed to see data.

    Per the interface map (stage 4.15), fitted transforms must
    declare a train-only fit scope; otherwise the build is blocked.
    ``TRAIN_ONLY`` is the default.
    """

    TRAIN_ONLY = "train_only"
    TRAIN_AND_HOLDOUT = "train_and_holdout"


class FeatureExclusionReason(str, Enum):
    """Catalogued reasons a row or column was excluded from the matrix."""

    HIGH_MISSINGNESS = "high_missingness"
    CONSTANT_COLUMN = "constant_column"
    NEAR_CONSTANT_COLUMN = "near_constant_column"
    DUPLICATE_COLUMN = "duplicate_column"
    LEAKAGE_PRONE = "leakage_prone"
    MULTICOLLINEARITY = "multicollinearity"
    USER_EXCLUDED = "user_excluded"
    MISSING_TARGET = "missing_target"
    OTHER = "other"


class LeakageRiskType(str, Enum):
    """Catalogued leakage risk types."""

    TARGET_AS_FEATURE = "target_as_feature"
    POST_OUTCOME_PREDICTOR = "post_outcome_predictor"
    TRAIN_TEST_CONTAMINATION = "train_test_contamination"
    DUPLICATE_COLUMN = "duplicate_column"
    OTHER = "other"


# ===========================================================================
# Task 28 - TargetSpec / FeatureSpec / SplitSpec / FeatureBuildRequest /
# FeatureEligibilityReport
# ===========================================================================
class TargetSpec(_FeaturesContractModel):
    """A typed target specification.

    Fields:

    - ``column_name``: :data:`ColumnName` of the target column.
    - ``task``: :class:`TargetTask`.
    - ``positive_class``: optional bounded positive-class label
      (only valid for CLASSIFICATION).
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ..., description="ColumnName of the target column."
    )
    task: TargetTask = Field(..., description="Target task type.")
    positive_class: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded positive-class label for binary classification.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _positive_class_consistent_with_task(self) -> "TargetSpec":
        if self.task is TargetTask.CLASSIFICATION:
            return self
        if self.positive_class is not None:
            raise ValueError(
                "TargetSpec.positive_class is only valid for CLASSIFICATION."
            )
        return self


class FeatureSpec(_FeaturesContractModel):
    """A typed feature specification.

    Fields:

    - ``column_name``: :data:`ColumnName` of the feature column.
    - ``role``: :class:`ColumnRole` (defaults to ``FEATURE``).
    - ``include_in_model``: whether the feature is included in the
      final model input.
    - ``required_for_eligibility``: when ``True`` (default), the
      column must be present for the spec to be eligible.
    - ``notes``: optional bounded human-readable note.
    """

    column_name: ColumnName = Field(
        ..., description="ColumnName of the feature column."
    )
    role: ColumnRole = Field(
        default=ColumnRole.FEATURE,
        description="ColumnRole. Defaults to FEATURE.",
    )
    include_in_model: bool = Field(
        default=True,
        description="Whether the feature is included in the final model input.",
    )
    required_for_eligibility: bool = Field(
        default=True,
        description="When True (default), the column must be present for the spec to be eligible.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


class SplitSpec(_FeaturesContractModel):
    """A typed data-split specification.

    Fields:

    - ``strategy``: :class:`SplitStrategy` (defaults to ``RANDOM``).
    - ``train_fraction`` / ``validation_fraction`` /
      ``test_fraction``: optional non-negative bounded ratios in
      ``[0.0, 1.0]``. When all three are set, they must sum to
      ``<= 1.0``.
    - ``holdout_fraction``: optional non-negative bounded holdout
      fraction (``0.0`` means "no holdout").
    - ``time_column``: optional :data:`ColumnName` (required when
      ``strategy == TIME``).
    - ``group_column``: optional :data:`ColumnName` (required when
      ``strategy == GROUP``).
    - ``stratify_column``: optional :data:`ColumnName` (required
      when ``strategy == STRATIFIED``).
    - ``seed``: optional non-negative random seed.
    - ``notes``: optional bounded human-readable note.
    """

    strategy: SplitStrategy = Field(
        default=SplitStrategy.RANDOM,
        description="SplitStrategy. Defaults to RANDOM.",
    )
    train_fraction: _BoundedRatio | None = Field(
        default=None,
        description="Optional non-negative bounded training fraction.",
    )
    validation_fraction: _BoundedRatio | None = Field(
        default=None,
        description="Optional non-negative bounded validation fraction.",
    )
    test_fraction: _BoundedRatio | None = Field(
        default=None,
        description="Optional non-negative bounded test fraction.",
    )
    holdout_fraction: _BoundedRatio = Field(
        default=0.0,
        description="Non-negative bounded holdout fraction. 0.0 means 'no holdout'.",
    )
    time_column: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName (required when strategy == TIME).",
    )
    group_column: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName (required when strategy == GROUP).",
    )
    stratify_column: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName (used when strategy == STRATIFIED).",
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative random seed.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _strategy_dependencies_consistent(self) -> "SplitSpec":
        if self.strategy is SplitStrategy.TIME and self.time_column is None:
            raise ValueError(
                "SplitSpec with strategy=TIME must include a time_column."
            )
        if self.strategy is SplitStrategy.GROUP and self.group_column is None:
            raise ValueError(
                "SplitSpec with strategy=GROUP must include a group_column."
            )
        if self.strategy is not SplitStrategy.TIME and self.time_column is not None:
            raise ValueError(
                "SplitSpec.time_column is only valid when strategy=TIME."
            )
        if self.strategy is not SplitStrategy.GROUP and self.group_column is not None:
            raise ValueError(
                "SplitSpec.group_column is only valid when strategy=GROUP."
            )
        if (
            self.strategy is SplitStrategy.STRATIFIED
            and self.stratify_column is None
        ):
            raise ValueError(
                "SplitSpec with strategy=STRATIFIED must include a stratify_column."
            )
        return self

    @model_validator(mode="after")
    def _fractions_sum_le_1(self) -> "SplitSpec":
        fractions = [
            f
            for f in (
                self.train_fraction,
                self.validation_fraction,
                self.test_fraction,
            )
            if f is not None
        ]
        if fractions and sum(fractions) > 1.0:
            raise ValueError(
                "SplitSpec train/validation/test fractions must sum to <= 1.0."
            )
        return self


class FeatureBuildRequest(_FeaturesContractModel):
    """A typed request to build a feature matrix.

    Fields:

    - ``dataset``: :class:`DatasetHandle`.
    - ``target``: :class:`TargetSpec`.
    - ``features``: tuple of :class:`FeatureSpec` (>= 1).
    - ``exclusions``: optional tuple of :data:`ColumnName`.
    - ``split``: :class:`SplitSpec`.
    - ``transformation_plan``: optional
      :class:`FeatureTransformationPlan`.
    - ``leakage_check``: optional :class:`LeakageCheckRequest`.
    - ``fit_scope``: :class:`PreprocessingFitScope` (defaults to
      ``TRAIN_ONLY``).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle of the source dataset.",
    )
    target: TargetSpec = Field(..., description="TargetSpec.")
    features: tuple[FeatureSpec, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of FeatureSpec (>= 1).",
    )
    exclusions: tuple[ColumnName, ...] = Field(
        default=(),
        description="Optional tuple of ColumnName explicitly excluded from modeling.",
    )
    split: SplitSpec = Field(
        default_factory=SplitSpec,
        description="SplitSpec.",
    )
    transformation_plan: "FeatureTransformationPlan | None" = Field(
        default=None,
        description="Optional FeatureTransformationPlan.",
    )
    leakage_check: "LeakageCheckRequest | None" = Field(
        default=None,
        description="Optional LeakageCheckRequest.",
    )
    fit_scope: PreprocessingFitScope = Field(
        default=PreprocessingFitScope.TRAIN_ONLY,
        description="PreprocessingFitScope. Defaults to TRAIN_ONLY.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _target_not_in_features(self) -> "FeatureBuildRequest":
        feature_names = {f.column_name for f in self.features}
        if self.target.column_name in feature_names:
            raise ValueError(
                "FeatureBuildRequest.target.column_name must not also "
                "appear in features."
            )
        return self

    @model_validator(mode="after")
    def _target_not_in_exclusions(self) -> "FeatureBuildRequest":
        if self.target.column_name in self.exclusions:
            raise ValueError(
                "FeatureBuildRequest.target.column_name must not also "
                "appear in exclusions."
            )
        return self

    @model_validator(mode="after")
    def _feature_column_names_unique(self) -> "FeatureBuildRequest":
        seen: set[str] = set()
        for f in self.features:
            if f.column_name in seen:
                raise ValueError(
                    f"FeatureBuildRequest.features has duplicate column names: {f.column_name!r}."
                )
            seen.add(f.column_name)
        return self

    @model_validator(mode="after")
    def _exclusions_unique(self) -> "FeatureBuildRequest":
        seen: set[str] = set()
        for col in self.exclusions:
            if col in seen:
                raise ValueError(
                    f"FeatureBuildRequest.exclusions has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


class FeatureEligibilityReport(_FeaturesContractModel):
    """The typed outcome of feature spec resolution (stage 4.13).

    Fields:

    - ``target_present``: whether the target column is present in
      the dataset.
    - ``missing_required_features``: tuple of :data:`ColumnName`
      for required features that are missing.
    - ``excluded_features``: tuple of :data:`ColumnName` for
      features that the user has excluded.
    - ``blocked_features``: tuple of :data:`ColumnName` for
      features that were blocked by upstream quality / leakage.
    - ``eligible``: whether the feature spec is eligible for matrix
      build.
    - ``block_reason``: optional bounded human-readable reason.
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    target_present: bool = Field(
        ...,
        description="Whether the target column is present in the dataset.",
    )
    missing_required_features: tuple[ColumnName, ...] = Field(
        default=(),
        description="Tuple of ColumnName for required features that are missing.",
    )
    excluded_features: tuple[ColumnName, ...] = Field(
        default=(),
        description="Tuple of ColumnName for features that the user has excluded.",
    )
    blocked_features: tuple[ColumnName, ...] = Field(
        default=(),
        description="Tuple of ColumnName for features that were blocked by upstream quality / leakage.",
    )
    eligible: bool = Field(
        default=True,
        description="Whether the feature spec is eligible for matrix build.",
    )
    block_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable reason. Populated when eligible is False.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during resolution (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during resolution (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _eligibility_consistent(self) -> "FeatureEligibilityReport":
        if not self.target_present and self.eligible:
            raise ValueError(
                "FeatureEligibilityReport with target_present=False must not "
                "have eligible=True."
            )
        if not self.eligible and not self.block_reason:
            raise ValueError(
                "FeatureEligibilityReport with eligible=False must include "
                "a non-empty block_reason."
            )
        if self.eligible and self.block_reason:
            raise ValueError(
                "FeatureEligibilityReport with eligible=True must not include "
                "a block_reason."
            )
        if self.missing_required_features and self.eligible:
            raise ValueError(
                "FeatureEligibilityReport with missing_required_features must "
                "have eligible=False."
            )
        return self

    @model_validator(mode="after")
    def _column_names_unique(self) -> "FeatureEligibilityReport":
        for field_name in (
            "missing_required_features",
            "excluded_features",
            "blocked_features",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(
                    f"FeatureEligibilityReport.{field_name} contains duplicate column names."
                )
        return self


# ===========================================================================
# Task 29 - FeatureTransformationPlan / Report
# ===========================================================================
class FeatureTransformationPlan(_FeaturesContractModel):
    """A typed plan for transforming features (stage 4.15 input).

    Fields:

    - ``plan_id``: stable identifier for the plan.
    - ``per_feature_steps``: tuple of
      ``(ColumnName, MissingValueStrategy, EncodingStrategy,
      ScalingStrategy)`` per feature. Each column appears at most
      once.
    - ``fit_scope``: :class:`PreprocessingFitScope` (defaults to
      ``TRAIN_ONLY``).
    - ``requires_holdout``: when ``True``, the plan requires a
      holdout split.
    - ``notes``: optional bounded human-readable note.
    """

    plan_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier for the plan.",
    )
    per_feature_steps: tuple[
        tuple[ColumnName, MissingValueStrategy, EncodingStrategy, ScalingStrategy],
        ...,
    ] = Field(
        default=(),
        description="Tuple of (ColumnName, MissingValueStrategy, EncodingStrategy, ScalingStrategy) per feature.",
    )
    fit_scope: PreprocessingFitScope = Field(
        default=PreprocessingFitScope.TRAIN_ONLY,
        description="PreprocessingFitScope. Defaults to TRAIN_ONLY.",
    )
    requires_holdout: bool = Field(
        default=False,
        description="When True, the plan requires a holdout split. Defaults to False.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _per_feature_steps_column_unique(self) -> "FeatureTransformationPlan":
        seen: set[str] = set()
        for col, *_ in self.per_feature_steps:
            if col in seen:
                raise ValueError(
                    f"FeatureTransformationPlan.per_feature_steps has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


class FeatureTransformationReport(_FeaturesContractModel):
    """The typed outcome of feature transformation (stage 4.15 output).

    Fields:

    - ``plan_id``: stable identifier of the plan that was executed.
    - ``executed_steps``: tuple of
      ``(ColumnName, MissingValueStrategy, EncodingStrategy,
      ScalingStrategy)`` describing the steps that actually ran.
    - ``skipped_steps``: tuple of ``(ColumnName, reason)``
      describing steps that were skipped.
    - ``fitted_artifact_id``: optional :data:`ArtifactId` referencing
      the persisted fitted-transform artifact.
    - ``fit_scope``: :class:`PreprocessingFitScope` actually used.
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    plan_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier of the plan that was executed.",
    )
    executed_steps: tuple[
        tuple[ColumnName, MissingValueStrategy, EncodingStrategy, ScalingStrategy],
        ...,
    ] = Field(
        default=(),
        description="Tuple of (ColumnName, MissingValueStrategy, EncodingStrategy, ScalingStrategy) actually executed.",
    )
    skipped_steps: tuple[tuple[ColumnName, str], ...] = Field(
        default=(),
        description="Tuple of (ColumnName, reason) for steps that were skipped.",
    )
    fitted_artifact_id: ArtifactId | None = Field(
        default=None,
        description="Optional ArtifactId referencing the persisted fitted-transform artifact.",
    )
    fit_scope: PreprocessingFitScope = Field(
        default=PreprocessingFitScope.TRAIN_ONLY,
        description="PreprocessingFitScope actually used. Defaults to TRAIN_ONLY.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during transformation (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during transformation (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _executed_column_names_unique(self) -> "FeatureTransformationReport":
        seen: set[str] = set()
        for col, *_ in self.executed_steps:
            if col in seen:
                raise ValueError(
                    f"FeatureTransformationReport.executed_steps has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self

    @model_validator(mode="after")
    def _skipped_column_names_unique(self) -> "FeatureTransformationReport":
        seen: set[str] = set()
        for col, _reason in self.skipped_steps:
            if col in seen:
                raise ValueError(
                    f"FeatureTransformationReport.skipped_steps has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


# ===========================================================================
# Task 30 - FeatureMatrixRef / Result / Rows / Columns reports
# ===========================================================================
class FeatureMatrixRef(_FeaturesContractModel):
    """A backend-neutral reference to a model-ready feature matrix.

    Fields:

    - ``matrix_id``: stable identifier for the matrix.
    - ``dataset_id``: :data:`DatasetId` of the source dataset.
    - ``row_count`` / ``column_count``: optional non-negative counts.
    - ``uri``: optional bounded uri/path of the persisted matrix.
    - ``fingerprint``: optional bounded content fingerprint.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    matrix_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier for the matrix.",
    )
    dataset_id: DatasetId = Field(
        ..., description="DatasetId of the source dataset."
    )
    row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative row count.",
    )
    column_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative column count.",
    )
    uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded uri/path of the persisted matrix.",
    )
    fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded content fingerprint.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None


class FeatureMatrixResult(_FeaturesContractModel):
    """The typed output of feature matrix build (stage 4.16).

    Fields:

    - ``matrix_ref``: :class:`FeatureMatrixRef` for the built matrix.
    - ``row_exclusions``: optional :class:`RowsExcludedReport`.
    - ``column_exclusions``: optional :class:`ColumnsExcludedReport`.
    - ``lineage_id``: optional :data:`LineageId` referencing the
      lineage record produced by the matrix build.
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    matrix_ref: FeatureMatrixRef = Field(
        ..., description="FeatureMatrixRef for the built matrix."
    )
    row_exclusions: "RowsExcludedReport | None" = Field(
        default=None,
        description="Optional RowsExcludedReport.",
    )
    column_exclusions: "ColumnsExcludedReport | None" = Field(
        default=None,
        description="Optional ColumnsExcludedReport.",
    )
    lineage_id: LineageId | None = Field(
        default=None,
        description="Optional LineageId referencing the lineage record produced by the matrix build.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during build (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during build (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class RowsExcludedReport(_FeaturesContractModel):
    """A typed report of rows excluded from the feature matrix.

    Fields:

    - ``excluded_row_count`` / ``total_row_count``: optional
      non-negative counts.
    - ``excluded_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``reason_breakdown``: optional tuple of
      ``(FeatureExclusionReason, count)``. Reasons are unique and
      counts are non-negative.
    - ``notes``: optional bounded human-readable note.
    """

    excluded_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of rows excluded.",
    )
    total_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total input rows.",
    )
    excluded_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded excluded ratio in [0.0, 1.0].",
    )
    reason_breakdown: tuple[tuple[FeatureExclusionReason, int], ...] = Field(
        default=(),
        description="Optional tuple of (FeatureExclusionReason, count) per reason.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _count_does_not_exceed_total(self) -> "RowsExcludedReport":
        if (
            self.excluded_row_count is not None
            and self.total_row_count is not None
            and self.excluded_row_count > self.total_row_count
        ):
            raise ValueError(
                "RowsExcludedReport.excluded_row_count must not exceed total_row_count."
            )
        return self

    @model_validator(mode="after")
    def _reason_breakdown_reasons_unique(self) -> "RowsExcludedReport":
        seen: set[FeatureExclusionReason] = set()
        for reason, _count in self.reason_breakdown:
            if reason in seen:
                raise ValueError(
                    f"RowsExcludedReport.reason_breakdown has duplicate reasons: {reason!r}."
                )
            seen.add(reason)
        return self

    @model_validator(mode="after")
    def _reason_breakdown_counts_non_negative(self) -> "RowsExcludedReport":
        for _reason, count in self.reason_breakdown:
            if count < 0:
                raise ValueError(
                    "RowsExcludedReport.reason_breakdown counts must be non-negative."
                )
        return self


class ColumnsExcludedReport(_FeaturesContractModel):
    """A typed report of columns excluded from the feature matrix.

    Fields:

    - ``excluded_column_count`` / ``total_column_count``: optional
      non-negative counts.
    - ``excluded_ratio``: optional bounded ratio in ``[0.0, 1.0]``.
    - ``per_column_reason``: optional tuple of
      ``(ColumnName, FeatureExclusionReason)``. Column names are
      unique.
    - ``notes``: optional bounded human-readable note.
    """

    excluded_column_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of columns excluded.",
    )
    total_column_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of total input columns.",
    )
    excluded_ratio: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded excluded ratio in [0.0, 1.0].",
    )
    per_column_reason: tuple[tuple[ColumnName, FeatureExclusionReason], ...] = Field(
        default=(),
        description="Optional tuple of (ColumnName, FeatureExclusionReason) per excluded column.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _count_does_not_exceed_total(self) -> "ColumnsExcludedReport":
        if (
            self.excluded_column_count is not None
            and self.total_column_count is not None
            and self.excluded_column_count > self.total_column_count
        ):
            raise ValueError(
                "ColumnsExcludedReport.excluded_column_count must not exceed total_column_count."
            )
        return self

    @model_validator(mode="after")
    def _per_column_reason_column_names_unique(self) -> "ColumnsExcludedReport":
        seen: set[str] = set()
        for col, _reason in self.per_column_reason:
            if col in seen:
                raise ValueError(
                    f"ColumnsExcludedReport.per_column_reason has duplicate column names: {col!r}."
                )
            seen.add(col)
        return self


# ===========================================================================
# Task 31 - LeakageCheckRequest / Risk / Report
# ===========================================================================
class LeakageCheckRequest(_FeaturesContractModel):
    """A typed request to run leakage checks (stage 4.17).

    Fields:

    - ``feature_build``: :class:`FeatureBuildRequest` that the
      leakage check is gating.
    - ``check_train_test_contamination``: when ``True`` (default),
      the leakage check verifies that no train-set statistic leaks
      into the holdout / test set.
    - ``check_post_outcome_predictors``: when ``True`` (default),
      the leakage check verifies that no feature is a
      ``post_outcome_predictor``.
    - ``fail_on_high_risk``: when ``True`` (default), HIGH-risk
      leakage findings block the matrix build.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    feature_build: FeatureBuildRequest = Field(
        ...,
        description="FeatureBuildRequest that the leakage check is gating.",
    )
    check_train_test_contamination: bool = Field(
        default=True,
        description="When True (default), the check verifies no train-statistic leaks into holdout/test.",
    )
    check_post_outcome_predictors: bool = Field(
        default=True,
        description="When True (default), the check verifies no feature is a post-outcome predictor.",
    )
    fail_on_high_risk: bool = Field(
        default=True,
        description="When True (default), HIGH-risk findings block the matrix build.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class LeakageRisk(_FeaturesContractModel):
    """A single leakage-risk finding.

    Fields:

    - ``column_name``: optional :data:`ColumnName` the risk refers to.
    - ``risk_type``: :class:`LeakageRiskType`.
    - ``severity``: :class:`Severity` of the risk.
    - ``score``: optional bounded score in ``[0.0, 1.0]``.
    - ``code``: optional bounded machine-readable code.
    - ``message``: human-readable message.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    column_name: ColumnName | None = Field(
        default=None,
        description="Optional ColumnName the risk refers to.",
    )
    risk_type: LeakageRiskType = Field(..., description="LeakageRiskType.")
    severity: Severity = Field(..., description="Severity of the risk.")
    score: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded score in [0.0, 1.0].",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional bounded machine-readable code.",
    )
    message: str = Field(..., min_length=1, description="Human-readable message.")
    run_id: RunId | None = None
    stage_id: StageId | None = None


class LeakageCheckReport(_FeaturesContractModel):
    """The typed output of stage 4.17 (leakage checks).

    Fields:

    - ``request``: the :class:`LeakageCheckRequest` that produced
      this report.
    - ``passed``: whether the leakage check passed.
    - ``risks``: tuple of :class:`LeakageRisk` (immutable).
    - ``block_reason``: optional bounded human-readable reason
      (populated when ``passed is False``).
    - ``target_as_feature_detected``: optional flag.
    - ``train_test_contamination_detected``: optional flag.
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    request: LeakageCheckRequest = Field(
        ...,
        description="LeakageCheckRequest that produced this report.",
    )
    passed: bool = Field(..., description="Whether the leakage check passed.")
    risks: tuple[LeakageRisk, ...] = Field(
        default=(),
        description="Tuple of LeakageRisk (immutable).",
    )
    block_reason: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable reason. Populated when passed is False.",
    )
    target_as_feature_detected: bool | None = Field(
        default=None,
        description="Optional flag indicating the target column was found in the feature set.",
    )
    train_test_contamination_detected: bool | None = Field(
        default=None,
        description="Optional flag indicating train-statistic leakage was detected.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during leakage check (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during leakage check (immutable).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _passed_consistent(self) -> "LeakageCheckReport":
        if self.passed and not self.risks and self.block_reason:
            raise ValueError(
                "LeakageCheckReport with passed=True and no risks must not "
                "include a block_reason."
            )
        if not self.passed and not self.block_reason:
            raise ValueError(
                "LeakageCheckReport with passed=False must include a "
                "non-empty block_reason."
            )
        return self

    @model_validator(mode="after")
    def _target_as_feature_flag_consistent(self) -> "LeakageCheckReport":
        if self.target_as_feature_detected is True and not any(
            risk.risk_type is LeakageRiskType.TARGET_AS_FEATURE
            for risk in self.risks
        ):
            raise ValueError(
                "LeakageCheckReport.target_as_feature_detected=True requires "
                "at least one TARGET_AS_FEATURE risk."
            )
        if self.train_test_contamination_detected is True and not any(
            risk.risk_type is LeakageRiskType.TRAIN_TEST_CONTAMINATION
            for risk in self.risks
        ):
            raise ValueError(
                "LeakageCheckReport.train_test_contamination_detected=True "
                "requires at least one TRAIN_TEST_CONTAMINATION risk."
            )
        return self


# Resolve forward references inside ``FeatureBuildRequest``.
FeatureBuildRequest.model_rebuild()
