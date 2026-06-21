"""Pipeline contracts (Build Queue v2.1 Tasks 42-45).

Public contracts for the ``pipeline`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Pipeline contracts describe
the typed shapes that cross stages 4.31-4.33 of the interface map
(analysis plan, run manifest, run result) plus the orchestration
metadata that lets the CLI display a finished run. They are
dependency-light: they import ``pydantic``, the standard library,
and the shared ``common`` / ``datasets`` / ``modeling`` /
``validation`` / ``registry`` contracts only. They never embed raw
dataframes, sample values, model objects, or backend objects.

Per the architecture-test plan (section 3.5), pipeline is the only
cross-module orchestrator. The contracts here are the typed
shapes that pipeline uses to drive domain modules through their
documented request/result contracts. Domain modules do not call
each other directly and do not import ``contracts/pipeline.py``.

Scope:

- ``PipelineStageName`` / ``PipelineExecutionMode`` /
  ``PipelineFailurePolicy`` enums (Task 42).
- ``AnalysisPlan`` typed config input (Task 42).
- ``RunManifestRequest`` / ``RunManifest`` (Task 44).
- ``PipelineWarningSummary`` (Task 42).
- ``AnalysisRunResult`` top-level run result (Task 45).
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
    ArtifactId,
    DatasetId,
    Issue,
    LineageId,
    ModelId,
    ReportId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.registry import (
    RegistryWriteRequest,
    RegistryWriteResult,
    RunStatus,
)

__all__ = [
    "PipelineStageName",
    "PipelineExecutionMode",
    "PipelineFailurePolicy",
    "AnalysisPlan",
    "RunManifestRequest",
    "RunManifest",
    "PipelineWarningSummary",
    "AnalysisRunResult",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _PipelineContractModel(BaseModel):
    """Base configuration for pipeline contracts.

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
class PipelineStageName(str, Enum):
    """Catalogued pipeline stage names (Task 42).

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. The order in this enum roughly mirrors
    the interface-map canonical stage list (4.1-4.33).
    """

    CONFIG_LOAD = "config_load"
    DATASET_LOAD = "dataset_load"
    DATASET_REGISTER = "dataset_register"
    SCHEMA_INFERENCE = "schema_inference"
    SEMANTIC_ROLE_INFERENCE = "semantic_role_inference"
    SCHEMA_VALIDATION = "schema_validation"
    DATA_QUALITY = "data_quality"
    DISTRIBUTION_PROFILING = "distribution_profiling"
    DIAGNOSTIC_ASSOCIATION = "diagnostic_association"
    JOIN_VALIDATION = "join_validation"
    JOIN_EXECUTION = "join_execution"
    FEATURE_SPEC_RESOLUTION = "feature_spec_resolution"
    FEATURE_SPLIT_PLANNING = "feature_split_planning"
    FEATURE_TRANSFORMATION_PLANNING = "feature_transformation_planning"
    FEATURE_MATRIX_BUILD = "feature_matrix_build"
    LEAKAGE_CHECKS = "leakage_checks"
    MODEL_SPEC_VALIDATION = "model_spec_validation"
    OLS_FIT = "ols_fit"
    OLS_RESULT_EXTRACTION = "ols_result_extraction"
    MODEL_FIT_METRICS = "model_fit_metrics"
    MODEL_DIAGNOSTICS = "model_diagnostics"
    MULTIPLE_TESTING_CORRECTION = "multiple_testing_correction"
    CLAIM_RULES = "claim_rules"
    ROBUSTNESS_STATUS = "robustness_status"
    MODEL_VALIDATION = "model_validation"
    REPORT_BUNDLE_ASSEMBLY = "report_bundle_assembly"
    REPORT_RENDERING = "report_rendering"
    VISUAL_ARTIFACT_GENERATION = "visual_artifact_generation"
    RUN_MANIFEST_WRITING = "run_manifest_writing"
    FILE_BASED_REGISTRY_WRITING = "file_based_registry_writing"
    CLI_RESULT_DISPLAY = "cli_result_display"


class PipelineExecutionMode(str, Enum):
    """Catalogued pipeline execution modes.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``REPLAY`` re-runs an existing run
    from its manifest; ``DRY_RUN`` validates the plan without
    executing; ``PROFILE_ONLY`` executes the stages up to (and
    including) the profile-only MVP checkpoint (Task 108).
    """

    NORMAL = "normal"
    DRY_RUN = "dry_run"
    REPLAY = "replay"
    PROFILE_ONLY = "profile_only"


class PipelineFailurePolicy(str, Enum):
    """Catalogued pipeline failure policies.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``FAIL_FAST`` aborts on the first
    block / ERROR-or-higher issue; ``CONTINUE_WITH_WARNINGS``
    runs all stages and records warnings.
    """

    FAIL_FAST = "fail_fast"
    CONTINUE_WITH_WARNINGS = "continue_with_warnings"


# ===========================================================================
# AnalysisPlan
# ===========================================================================
class AnalysisPlan(_PipelineContractModel):
    """A typed top-level analysis plan (Task 42 / 43).

    An ``AnalysisPlan`` is the canonical input to the pipeline
    (stage 4.1: config loading). It pairs the bounded
    configuration with the dataset(s) to operate on, the model
    spec, the splits, and the pipeline-level options. It must
    not reference raw dataframes, sample values, or backend
    objects.

    Fields:

    - ``plan_id``: stable identifier for the plan.
    - ``datasets``: tuple of :class:`DatasetHandle` (>= 1).
    - ``stages``: tuple of :class:`PipelineStageName` to execute
      (>= 1). Optional stages are listed only when they are
      selected.
    - ``execution_mode``: :class:`PipelineExecutionMode`
      (defaults to ``NORMAL``).
    - ``failure_policy``: :class:`PipelineFailurePolicy`
      (defaults to ``FAIL_FAST``).
    - ``target_dataset_index``: optional non-negative index of
      the dataset to use as the modeling target. ``None`` means
      "use the only dataset in the plan".
    - ``config_hash``: optional bounded hash of the resolved
      configuration. ``None`` means "computed at run time".
    - ``max_runtime_seconds``: optional non-negative upper bound
      on the total pipeline runtime.
    - ``notes``: optional bounded human-readable note.
    """

    plan_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier for the plan.",
    )
    datasets: tuple[DatasetHandle, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of DatasetHandle (>= 1).",
    )
    stages: tuple[PipelineStageName, ...] = Field(
        ...,
        min_length=1,
        description="Tuple of PipelineStageName to execute (>= 1).",
    )
    execution_mode: PipelineExecutionMode = Field(
        default=PipelineExecutionMode.NORMAL,
        description="PipelineExecutionMode. Defaults to NORMAL.",
    )
    failure_policy: PipelineFailurePolicy = Field(
        default=PipelineFailurePolicy.FAIL_FAST,
        description="PipelineFailurePolicy. Defaults to FAIL_FAST.",
    )
    target_dataset_index: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative index of the target dataset.",
    )
    config_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded hash of the resolved configuration.",
    )
    max_runtime_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on total pipeline runtime.",
    )
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _target_dataset_index_in_range(self) -> "AnalysisPlan":
        if self.target_dataset_index is not None and self.target_dataset_index >= len(
            self.datasets
        ):
            raise ValueError(
                "AnalysisPlan.target_dataset_index must be within range of "
                "the datasets tuple."
            )
        return self

    @model_validator(mode="after")
    def _stages_unique(self) -> "AnalysisPlan":
        seen: set[PipelineStageName] = set()
        for stage in self.stages:
            if stage in seen:
                raise ValueError(
                    f"AnalysisPlan.stages has duplicate stage: {stage!r}."
                )
            seen.add(stage)
        return self


# ===========================================================================
# RunManifest
# ===========================================================================
class RunManifestRequest(_PipelineContractModel):
    """A typed request to write a run manifest (stage 4.31 input).

    Fields:

    - ``plan``: :class:`AnalysisPlan` to write the manifest for.
    - ``dataset_fingerprints``: optional tuple of
      ``(DatasetId, fingerprint)`` per dataset.
    - ``config_hash``: optional bounded config hash.
    - ``lineage_snapshot_id``: optional :data:`LineageId`.
    - ``artifact_ids``: optional tuple of :data:`ArtifactId`
      produced by the run.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    plan: AnalysisPlan = Field(..., description="AnalysisPlan to write the manifest for.")
    dataset_fingerprints: tuple[tuple[DatasetId, str], ...] = Field(
        default=(),
        description="Optional tuple of (DatasetId, fingerprint) per dataset.",
    )
    config_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded config hash.",
    )
    lineage_snapshot_id: LineageId | None = Field(
        default=None,
        description="Optional LineageId.",
    )
    artifact_ids: tuple[ArtifactId, ...] = Field(
        default=(),
        description="Optional tuple of ArtifactId produced by the run.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class RunManifest(_PipelineContractModel):
    """A typed run manifest (stage 4.31 output).

    Per the interface map, a run manifest references the config
    hash, dataset fingerprints, artifacts, and stage statuses.

    Fields:

    - ``manifest_id``: stable identifier.
    - ``run_id``: :data:`RunId` of the run.
    - ``plan``: :class:`AnalysisPlan` that was executed.
    - ``config_hash``: optional bounded config hash.
    - ``dataset_fingerprints``: tuple of
      ``(DatasetId, fingerprint)`` per dataset.
    - ``lineage_snapshot_id``: optional :data:`LineageId`.
    - ``artifact_ids``: tuple of :data:`ArtifactId`.
    - ``model_ids``: tuple of :data:`ModelId`.
    - ``report_ids``: tuple of :data:`ReportId`.
    - ``stage_statuses``: optional tuple of
      ``(StageId, RunStatus)`` per stage.
    - ``started_at`` / ``finished_at``: optional timezone-aware
      timestamps.
    - ``issues`` / ``warnings``: common typed collections.
    - ``run_id_loc`` / ``stage_id_loc``: optional provenance
      locators (named to avoid shadowing the run_id field).
    - ``metadata``: small bounded string-to-string metadata.
    """

    manifest_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    run_id: RunId = Field(..., description="RunId of the run.")
    plan: AnalysisPlan = Field(
        ..., description="AnalysisPlan that was executed."
    )
    config_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional bounded config hash.",
    )
    dataset_fingerprints: tuple[tuple[DatasetId, str], ...] = Field(
        default=(),
        description="Tuple of (DatasetId, fingerprint) per dataset.",
    )
    lineage_snapshot_id: LineageId | None = Field(
        default=None,
        description="Optional LineageId.",
    )
    artifact_ids: tuple[ArtifactId, ...] = Field(
        default=(),
        description="Tuple of ArtifactId.",
    )
    model_ids: tuple[ModelId, ...] = Field(
        default=(),
        description="Tuple of ModelId.",
    )
    report_ids: tuple[ReportId, ...] = Field(
        default=(),
        description="Tuple of ReportId.",
    )
    stage_statuses: tuple[tuple[StageId, RunStatus], ...] = Field(
        default=(),
        description="Optional tuple of (StageId, RunStatus) per stage.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run start.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run finish.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during the run (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during the run (immutable).",
    )
    run_id_loc: RunId | None = Field(
        default=None,
        description="Optional provenance RunId (re-exported to avoid shadowing).",
    )
    stage_id_loc: StageId | None = Field(
        default=None,
        description="Optional provenance StageId (re-exported to avoid shadowing).",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _stage_statuses_unique(self) -> "RunManifest":
        seen: set[str] = set()
        for stage_id, _status in self.stage_statuses:
            if stage_id in seen:
                raise ValueError(
                    f"RunManifest has duplicate stage_id in stage_statuses: {stage_id!r}."
                )
            seen.add(stage_id)
        return self

    @model_validator(mode="after")
    def _timestamps_timezone_aware(self) -> "RunManifest":
        for field_name in ("started_at", "finished_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(
                    self, field_name, value.replace(tzinfo=timezone.utc)
                )
        return self

    @model_validator(mode="after")
    def _finished_after_started(self) -> "RunManifest":
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError(
                "RunManifest.finished_at must be >= started_at."
            )
        return self


# ===========================================================================
# PipelineWarningSummary
# ===========================================================================
class PipelineWarningSummary(_PipelineContractModel):
    """A typed per-warning summary for the run (Task 42).

    Fields:

    - ``total_warning_count``: optional non-negative count of
      warnings emitted across the run.
    - ``warnings_by_severity``: optional tuple of
      ``(Severity, count)``. Severities are unique.
    - ``skipped_stage_count``: optional non-negative count of
      stages that were skipped.
    - ``blocked_stage_count``: optional non-negative count of
      stages that were blocked.
    - ``notes``: optional bounded human-readable note.
    """

    total_warning_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of warnings emitted across the run.",
    )
    warnings_by_severity: tuple[tuple[Severity, int], ...] = Field(
        default=(),
        description="Optional tuple of (Severity, count). Severities are unique.",
    )
    skipped_stage_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of stages that were skipped.",
    )
    blocked_stage_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of stages that were blocked.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _severities_unique(self) -> "PipelineWarningSummary":
        seen: set[Severity] = set()
        for severity, _count in self.warnings_by_severity:
            if severity in seen:
                raise ValueError(
                    f"PipelineWarningSummary has duplicate severity: {severity!r}."
                )
            seen.add(severity)
        return self

    @model_validator(mode="after")
    def _counts_non_negative(self) -> "PipelineWarningSummary":
        for _severity, count in self.warnings_by_severity:
            if count < 0:
                raise ValueError(
                    "PipelineWarningSummary warnings_by_severity counts must "
                    "be non-negative."
                )
        return self


# ===========================================================================
# AnalysisRunResult
# ===========================================================================
class AnalysisRunResult(_PipelineContractModel):
    """The typed top-level run result (Task 45).

    Per the architecture-test plan (section 3.6), the CLI produces
    terminal status and artifact paths from this contract only. The
    CLI is a thin wrapper and does not call domain modules
    directly; it goes through pipeline, which produces this result.

    Fields:

    - ``run_id``: :data:`RunId` of the run.
    - ``status``: :class:`RunStatus` of the run.
    - ``plan``: :class:`AnalysisPlan` that was executed.
    - ``manifest``: optional :class:`RunManifest`.
    - ``registry_write``: optional :class:`RegistryWriteResult`.
    - ``report_ids``: optional tuple of :data:`ReportId`.
    - ``artifact_paths``: optional tuple of bounded strings
      (artifact uri/path values).
    - ``warning_summary``: optional
      :class:`PipelineWarningSummary`.
    - ``issues`` / ``warnings``: common typed collections.
    - ``started_at`` / ``finished_at``: optional timezone-aware
      timestamps.
    - ``run_id_loc`` / ``stage_id_loc``: optional provenance
      locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    run_id: RunId = Field(..., description="RunId of the run.")
    status: RunStatus = Field(..., description="RunStatus of the run.")
    plan: AnalysisPlan = Field(
        ..., description="AnalysisPlan that was executed."
    )
    manifest: RunManifest | None = Field(
        default=None,
        description="Optional RunManifest.",
    )
    registry_write: RegistryWriteResult | None = Field(
        default=None,
        description="Optional RegistryWriteResult.",
    )
    report_ids: tuple[ReportId, ...] = Field(
        default=(),
        description="Optional tuple of ReportId.",
    )
    artifact_paths: tuple[str, ...] = Field(
        default=(),
        description="Optional tuple of bounded artifact uri/path values.",
    )
    warning_summary: PipelineWarningSummary | None = Field(
        default=None,
        description="Optional PipelineWarningSummary.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during the run (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during the run (immutable).",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run start.",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of run finish.",
    )
    run_id_loc: RunId | None = Field(
        default=None,
        description="Optional provenance RunId (re-exported to avoid shadowing).",
    )
    stage_id_loc: StageId | None = Field(
        default=None,
        description="Optional provenance StageId (re-exported to avoid shadowing).",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _registry_write_run_id_matches(self) -> "AnalysisRunResult":
        if (
            self.registry_write is not None
            and self.registry_write.run_id != self.run_id
        ):
            raise ValueError(
                "AnalysisRunResult.registry_write.run_id must equal "
                "AnalysisRunResult.run_id."
            )
        return self

    @model_validator(mode="after")
    def _artifact_paths_bounded(self) -> "AnalysisRunResult":
        for path in self.artifact_paths:
            if not path or len(path) > 2048:
                raise ValueError(
                    "AnalysisRunResult.artifact_paths entries must be "
                    "non-empty and <= 2048 characters."
                )
        return self

    @model_validator(mode="after")
    def _timestamps_timezone_aware(self) -> "AnalysisRunResult":
        for field_name in ("started_at", "finished_at"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                object.__setattr__(
                    self, field_name, value.replace(tzinfo=timezone.utc)
                )
        return self

    @model_validator(mode="after")
    def _finished_after_started(self) -> "AnalysisRunResult":
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError(
                "AnalysisRunResult.finished_at must be >= started_at."
            )
        return self

    @model_validator(mode="after")
    def _report_ids_unique(self) -> "AnalysisRunResult":
        seen: set[str] = set()
        for rid in self.report_ids:
            if rid in seen:
                raise ValueError(
                    f"AnalysisRunResult.report_ids has duplicate report_id: {rid!r}."
                )
            seen.add(rid)
        return self
