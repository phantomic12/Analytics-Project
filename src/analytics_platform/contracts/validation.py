"""Validation contracts (Build Queue v2.1 Tasks 36-38).

Public contracts for the ``validation`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Validation contracts
describe the typed shapes that cross stages 4.25-4.27 of the
interface map (claim rules and causal blocking, robustness status,
model validation). They are dependency-light: they import
``pydantic``, the standard library, and the shared ``common`` /
``schemas`` / ``semantics`` / ``features`` / ``modeling`` contracts
only. They never embed raw dataframes, sample values, model
objects, or backend objects.

Per the interface map:

- 4.25 (claim rules and causal blocking): ``ClaimLevel`` /
  ``EvidenceGrade`` / ``CausalWarning`` /
  ``ApprovedWording`` / ``DisallowedWording``. Causal claim level
  is blocked in MVP; weak evidence is downgraded, not silently
  emitted.
- 4.26 (robustness status): ``RobustnessCheckSpec`` /
  ``RobustnessCheckResult`` / ``SkippedRobustnessCheck``. Skipped
  checks are emitted as typed skipped records, not omitted.
- 4.27 (model validation): ``ValidationSpec`` /
  ``ModelValidationRequest`` / ``ModelValidationReport`` /
  ``ValidatedModelInterpretation`` /
  ``RejectedModelInterpretation``. Causal claims are rejected;
  unsupported outputs are downgraded and visible; blocks produce
  typed reasons.

Scope:

- ``ClaimLevel`` / ``EvidenceGrade`` / ``CausalClaimPolicy`` enums.
- ``CausalWarning`` / ``ApprovedWording`` / ``DisallowedWording`` models.
- ``ValidationStrategy`` enum.
- ``RobustnessCheckSpec`` / ``RobustnessCheckResult`` /
  ``SkippedRobustnessCheck`` models.
- ``ValidationSpec`` / ``ModelValidationRequest`` /
  ``ModelValidationReport`` /
  ``ValidatedModelInterpretation`` /
  ``RejectedModelInterpretation`` models.
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
    ModelId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.modeling import ModelDiagnosticReport, ModelResult
from analytics_platform.contracts.statistics import MultipleTestingCorrectionReport

__all__ = [
    # Task 36
    "ClaimLevel",
    "EvidenceGrade",
    "CausalClaimPolicy",
    "CausalWarning",
    "ApprovedWording",
    "DisallowedWording",
    "ValidationStrategy",
    # Task 37
    "RobustnessCheckSpec",
    "RobustnessCheckResult",
    "SkippedRobustnessCheck",
    # Task 38
    "ValidationSpec",
    "ModelValidationRequest",
    "ModelValidationReport",
    "ValidatedModelInterpretation",
    "RejectedModelInterpretation",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ValidationContractModel(BaseModel):
    """Base configuration for validation contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``). They never embed raw dataframes, sample
    values, model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for confidence levels.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Task 36 — Claim levels, evidence, causal policy
# ===========================================================================
class ClaimLevel(str, Enum):
    """Catalogued claim levels for validated interpretations.

    Per the interface map, causal claim level is blocked in MVP.
    Ordered from most-claim to least-claim:

    - ``CAUSAL`` (blocked in MVP).
    - ``QUASI_CAUSAL`` (blocked in MVP).
    - ``EXPLANATORY`` (associational, with explicit caveats).
    - ``DESCRIPTIVE`` (pattern description, no causal implication).
    - ``EXPLORATORY`` (hypothesis-generating only).
    """

    CAUSAL = "causal"
    QUASI_CAUSAL = "quasi_causal"
    EXPLANATORY = "explanatory"
    DESCRIPTIVE = "descriptive"
    EXPLORATORY = "exploratory"


class EvidenceGrade(str, Enum):
    """Catalogued evidence grades for validated interpretations.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries.
    """

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class CausalClaimPolicy(str, Enum):
    """Policy for causal-claim handling.

    Per the interface map, causal claim level is blocked in MVP.
    ``BLOCK`` rejects any causal / quasi-causal claim;
    ``DOWNGRADE`` rewrites causal claims to ``EXPLANATORY``
    (associational, with explicit caveats); ``ALLOW`` permits
    causal claims (not used in MVP).
    """

    BLOCK = "block"
    DOWNGRADE = "downgrade"
    ALLOW = "allow"


class CausalWarning(_ValidationContractModel):
    """A typed causal-claim warning.

    A causal warning is raised when an interpretation claims
    causation but the underlying evidence does not support it. The
    warning is advisory — it does not block the pipeline by
    itself, but is surfaced to reporting.

    Fields:

    - ``code``: stable machine-readable code.
    - ``severity``: :class:`Severity` of the warning.
    - ``message``: human-readable message.
    - ``attempted_claim_level``: :class:`ClaimLevel` the
      interpretation attempted (typically ``CAUSAL`` or
      ``QUASI_CAUSAL``).
    - ``downgraded_to``: :class:`ClaimLevel` the interpretation
      was downgraded to (typically ``EXPLANATORY`` or
      ``DESCRIPTIVE``).
    - ``related_claim_text``: optional bounded quoted text that
      triggered the warning.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable code.",
    )
    severity: Severity = Field(..., description="Severity of the warning.")
    message: str = Field(..., min_length=1, description="Human-readable message.")
    attempted_claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel the interpretation attempted.",
    )
    downgraded_to: ClaimLevel = Field(
        ...,
        description="ClaimLevel the interpretation was downgraded to.",
    )
    related_claim_text: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded quoted text that triggered the warning.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None

    @model_validator(mode="after")
    def _downgrade_target_valid(self) -> "CausalWarning":
        # The downgraded-to level must be at most as strong as the
        # attempted level. ``CAUSAL`` and ``QUASI_CAUSAL`` are the
        # only levels that may trigger a causal warning; the
        # downgrade must be strictly weaker.
        weaker_or_equal = {
            ClaimLevel.CAUSAL: {
                ClaimLevel.QUASI_CAUSAL,
                ClaimLevel.EXPLANATORY,
                ClaimLevel.DESCRIPTIVE,
                ClaimLevel.EXPLORATORY,
            },
            ClaimLevel.QUASI_CAUSAL: {
                ClaimLevel.EXPLANATORY,
                ClaimLevel.DESCRIPTIVE,
                ClaimLevel.EXPLORATORY,
            },
        }
        allowed = weaker_or_equal.get(self.attempted_claim_level, set())
        if self.downgraded_to not in allowed:
            raise ValueError(
                f"CausalWarning.downgraded_to={self.downgraded_to!r} is not a "
                f"valid downgrade from attempted_claim_level="
                f"{self.attempted_claim_level!r}."
            )
        return self


class ApprovedWording(_ValidationContractModel):
    """A typed approved-wording record for a claim level.

    Approved wording records the bounded text that is allowed for a
    given claim level, paired with the evidence grade that supports
    it. Approved wording is consumed by reporting; it is advisory
    and does not block the pipeline.

    Fields:

    - ``claim_level``: :class:`ClaimLevel` this wording is
      approved for.
    - ``min_evidence_grade``: :class:`EvidenceGrade` required
      for this wording.
    - ``text``: bounded approved text.
    - ``context``: small bounded string-to-string metadata.
    """

    claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel this wording is approved for.",
    )
    min_evidence_grade: EvidenceGrade = Field(
        ...,
        description="EvidenceGrade required for this wording.",
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded approved text.",
    )
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class DisallowedWording(_ValidationContractModel):
    """A typed disallowed-wording record for a claim level.

    Disallowed wording records the bounded text that is *not*
    allowed for a given claim level. Reporting may use it as a
    blacklist when generating narrative output.

    Fields:

    - ``claim_level``: :class:`ClaimLevel` this wording is
      disallowed for.
    - ``pattern``: bounded disallowed text or pattern.
    - ``reason``: bounded human-readable reason.
    - ``context``: small bounded string-to-string metadata.
    """

    claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel this wording is disallowed for.",
    )
    pattern: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded disallowed text or pattern.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded human-readable reason.",
    )
    context: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class ValidationStrategy(str, Enum):
    """Catalogued model validation strategies.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries.
    """

    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    EXPLORATORY = "exploratory"


# ===========================================================================
# Task 37 — Robustness check
# ===========================================================================
class RobustnessCheckSpec(_ValidationContractModel):
    """A bounded spec for what the robustness stage should run.

    Fields:

    - ``min_sample_perturbation_fraction``: optional bounded
      fraction in ``[0.0, 1.0]``. When set, the stage may perturb
      the sample by up to this fraction and re-run a check.
    - ``max_severe_violations``: optional non-negative upper bound
      on the count of severe assumption violations tolerated before
      the model is considered unstable.
    - ``require_holdout``: when ``True``, the robustness stage
      requires a holdout. Defaults to ``True``.
    - ``notes``: optional bounded human-readable note.
    """

    min_sample_perturbation_fraction: _BoundedRatio | None = Field(
        default=None,
        description="Optional bounded fraction in [0.0, 1.0].",
    )
    max_severe_violations: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative upper bound on severe assumption violations.",
    )
    require_holdout: bool = Field(
        default=True,
        description="When True (default), the robustness stage requires a holdout.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


class RobustnessCheckResult(_ValidationContractModel):
    """A single robustness-check result (Task 37).

    Fields:

    - ``check_name``: stable name of the robustness check
      (``"coefficient_stability_under_perturbation"`` / etc.).
    - ``passed``: whether the check passed.
    - ``observed_metric``: optional real-number metric observed
      (e.g. coefficient drift, R^2 change).
    - ``threshold``: optional real-number threshold.
    - ``severity``: :class:`Severity` of the result.
    - ``message``: human-readable message.
    """

    check_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable name of the robustness check.",
    )
    passed: bool = Field(..., description="Whether the check passed.")
    observed_metric: float | None = Field(
        default=None,
        description="Optional real-number metric observed.",
    )
    threshold: float | None = Field(
        default=None, description="Optional real-number threshold."
    )
    severity: Severity = Field(..., description="Severity of the result.")
    message: str = Field(..., min_length=1, description="Human-readable message.")


class SkippedRobustnessCheck(_ValidationContractModel):
    """A typed skipped-record for a robustness check (Task 37).

    Per the interface map, skipped checks are emitted as typed
    skipped records, not omitted.

    Fields:

    - ``check_name``: stable name of the check that was skipped.
    - ``reason``: bounded human-readable reason.
    - ``severity``: :class:`Severity` of the skip (typically
      ``INFO`` or ``WARNING``).
    """

    check_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable name of the check that was skipped.",
    )
    reason: str = Field(
        ..., min_length=1, max_length=4096, description="Bounded human-readable reason."
    )
    severity: Severity = Field(
        default=Severity.WARNING,
        description="Severity of the skip. Defaults to WARNING.",
    )


# ===========================================================================
# Task 38 — Model validation request / report / interpretations
# ===========================================================================
class ValidationSpec(_ValidationContractModel):
    """A bounded spec for the model validation stage.

    Fields:

    - ``strategy``: :class:`ValidationStrategy` (defaults to
      ``STANDARD``).
    - ``causal_claim_policy``: :class:`CausalClaimPolicy` (defaults
      to ``BLOCK``; the MVP blocks causal claims).
    - ``max_allowed_claim_level``: :class:`ClaimLevel` the stage
      may emit (defaults to ``EXPLANATORY``; the MVP blocks
      ``CAUSAL`` / ``QUASI_CAUSAL``).
    - ``min_evidence_grade``: :class:`EvidenceGrade` required
      for any emitted claim (defaults to ``MODERATE``).
    - ``fail_on_rejection``: when ``True`` (default), a rejected
      interpretation blocks the model.
    - ``notes``: optional bounded human-readable note.
    """

    strategy: ValidationStrategy = Field(
        default=ValidationStrategy.STANDARD,
        description="ValidationStrategy. Defaults to STANDARD.",
    )
    causal_claim_policy: CausalClaimPolicy = Field(
        default=CausalClaimPolicy.BLOCK,
        description="CausalClaimPolicy. Defaults to BLOCK (MVP blocks causal claims).",
    )
    max_allowed_claim_level: ClaimLevel = Field(
        default=ClaimLevel.EXPLANATORY,
        description="Maximum ClaimLevel the stage may emit. Defaults to EXPLANATORY.",
    )
    min_evidence_grade: EvidenceGrade = Field(
        default=EvidenceGrade.MODERATE,
        description="Minimum EvidenceGrade required. Defaults to MODERATE.",
    )
    fail_on_rejection: bool = Field(
        default=True,
        description="When True (default), a rejected interpretation blocks the model.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _causal_levels_blocked_in_mvp(self) -> "ValidationSpec":
        if self.causal_claim_policy is CausalClaimPolicy.ALLOW:
            raise ValueError(
                "ValidationSpec.causal_claim_policy=ALLOW is not allowed "
                "in the v1.1 MVP. Use BLOCK or DOWNGRADE."
            )
        if self.max_allowed_claim_level in (
            ClaimLevel.CAUSAL,
            ClaimLevel.QUASI_CAUSAL,
        ):
            raise ValueError(
                "ValidationSpec.max_allowed_claim_level=CAUSAL or QUASI_CAUSAL "
                "is not allowed in the v1.1 MVP."
            )
        return self


class ModelValidationRequest(_ValidationContractModel):
    """A typed request to validate a model (stage 4.27 input).

    Fields:

    - ``model_id``: :data:`ModelId` of the model being validated.
    - ``result``: :class:`ModelResult` produced by the fit.
    - ``diagnostics``: :class:`ModelDiagnosticReport` for the
      model.
    - ``multiple_testing_correction``: optional
      :class:`MultipleTestingCorrectionReport` for the family
      the model belongs to.
    - ``robustness_checks``: tuple of
      :class:`RobustnessCheckResult` already run (advisory).
    - ``skipped_robustness_checks``: tuple of
      :class:`SkippedRobustnessCheck`.
    - ``spec``: :class:`ValidationSpec`.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    model_id: ModelId = Field(..., description="ModelId of the model being validated.")
    result: ModelResult = Field(..., description="ModelResult produced by the fit.")
    diagnostics: ModelDiagnosticReport = Field(
        ..., description="ModelDiagnosticReport for the model."
    )
    multiple_testing_correction: MultipleTestingCorrectionReport | None = Field(
        default=None,
        description="Optional MultipleTestingCorrectionReport for the model family.",
    )
    robustness_checks: tuple[RobustnessCheckResult, ...] = Field(
        default=(),
        description="Tuple of RobustnessCheckResult already run (advisory).",
    )
    skipped_robustness_checks: tuple[SkippedRobustnessCheck, ...] = Field(
        default=(),
        description="Tuple of SkippedRobustnessCheck.",
    )
    spec: ValidationSpec = Field(
        default_factory=ValidationSpec,
        description="ValidationSpec. Defaults to a STANDARD / BLOCK spec.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _result_model_id_matches(self) -> "ModelValidationRequest":
        if self.result.model_id != self.model_id:
            raise ValueError(
                "ModelValidationRequest.result.model_id must equal "
                "ModelValidationRequest.model_id."
            )
        if self.diagnostics.model_id != self.model_id:
            raise ValueError(
                "ModelValidationRequest.diagnostics.model_id must equal "
                "ModelValidationRequest.model_id."
            )
        return self

    @model_validator(mode="after")
    def _robustness_check_names_unique(self) -> "ModelValidationRequest":
        seen: set[str] = set()
        for c in self.robustness_checks:
            if c.check_name in seen:
                raise ValueError(
                    f"ModelValidationRequest.robustness_checks has duplicate check_name: {c.check_name!r}."
                )
            seen.add(c.check_name)
        return self

    @model_validator(mode="after")
    def _skipped_robustness_check_names_unique(self) -> "ModelValidationRequest":
        seen: set[str] = set()
        for c in self.skipped_robustness_checks:
            if c.check_name in seen:
                raise ValueError(
                    f"ModelValidationRequest.skipped_robustness_checks has duplicate check_name: {c.check_name!r}."
                )
            seen.add(c.check_name)
        return self


class ValidatedModelInterpretation(_ValidationContractModel):
    """A typed validated model interpretation (Task 38 output).

    Per the interface map, a validated interpretation carries
    the bounded claim level, the evidence grade, the bounded
    approved wording, the optional causal warnings, and the typed
    issues / warnings.

    Fields:

    - ``interpretation_id``: stable identifier.
    - ``claim_level``: :class:`ClaimLevel` actually emitted.
    - ``evidence_grade``: :class:`EvidenceGrade` actually
      supported.
    - ``approved_wording``: bounded approved text.
    - ``causal_warnings``: tuple of :class:`CausalWarning`.
    - ``issues`` / ``warnings``: common typed collections.
    - ``notes``: optional bounded human-readable note.
    """

    interpretation_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel actually emitted.",
    )
    evidence_grade: EvidenceGrade = Field(
        ...,
        description="EvidenceGrade actually supported.",
    )
    approved_wording: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded approved text.",
    )
    causal_warnings: tuple[CausalWarning, ...] = Field(
        default=(),
        description="Tuple of CausalWarning (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
    )
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )


class RejectedModelInterpretation(_ValidationContractModel):
    """A typed rejected model interpretation (Task 38 output).

    Per the interface map, unsupported outputs are downgraded and
    visible; blocks produce typed reasons. A rejected interpretation
    is the typed block record; the rejected wording is preserved so
    reporting can display the rejection.

    Fields:

    - ``interpretation_id``: stable identifier.
    - ``attempted_claim_level``: :class:`ClaimLevel` the
      interpretation attempted.
    - ``rejection_reason_code``: stable machine-readable code.
    - ``rejection_reason_message``: bounded human-readable
      reason.
    - ``rejected_wording``: bounded text that was rejected.
    - ``causal_warnings``: tuple of :class:`CausalWarning`.
    - ``issues`` / ``warnings``: common typed collections.
    """

    interpretation_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    attempted_claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel the interpretation attempted.",
    )
    rejection_reason_code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable machine-readable rejection code.",
    )
    rejection_reason_message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded human-readable rejection reason.",
    )
    rejected_wording: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Bounded text that was rejected.",
    )
    causal_warnings: tuple[CausalWarning, ...] = Field(
        default=(),
        description="Tuple of CausalWarning (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
    )


class ModelValidationReport(_ValidationContractModel):
    """The typed output of stage 4.27 (model validation).

    Per the interface map, a model validation report carries:

    - the request that produced the report,
    - the per-interpretation validated and rejected records,
    - the typed causal warnings,
    - the typed issues / warnings,
    - a few convenience summary fields.

    Causal claims are rejected; unsupported outputs are downgraded
    and visible; blocks produce typed reasons.

    Fields:

    - ``request``: the :class:`ModelValidationRequest` that
      produced this report.
    - ``validated``: tuple of :class:`ValidatedModelInterpretation`
      (immutable; may be empty when everything is rejected).
    - ``rejected``: tuple of :class:`RejectedModelInterpretation`
      (immutable; may be empty).
    - ``overall_passed``: whether the model as a whole passed
      validation. ``True`` when no rejections triggered a block.
    - ``causal_warnings``: tuple of :class:`CausalWarning` across
      all interpretations (immutable).
    - ``issues`` / ``warnings_records``: common typed collections.
    - ``computed_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    request: ModelValidationRequest = Field(
        ...,
        description="ModelValidationRequest that produced this report.",
    )
    validated: tuple[ValidatedModelInterpretation, ...] = Field(
        default=(),
        description="Tuple of ValidatedModelInterpretation (immutable).",
    )
    rejected: tuple[RejectedModelInterpretation, ...] = Field(
        default=(),
        description="Tuple of RejectedModelInterpretation (immutable).",
    )
    overall_passed: bool = Field(
        ...,
        description="Whether the model as a whole passed validation.",
    )
    causal_warnings: tuple[CausalWarning, ...] = Field(
        default=(),
        description="Tuple of CausalWarning across all interpretations (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during validation (immutable).",
    )
    warnings_records: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during validation (immutable).",
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
    def _interpretation_ids_unique(self) -> "ModelValidationReport":
        seen: set[str] = set()
        for v in self.validated:
            if v.interpretation_id in seen:
                raise ValueError(
                    f"ModelValidationReport.validated has duplicate interpretation_id: {v.interpretation_id!r}."
                )
            seen.add(v.interpretation_id)
        for r in self.rejected:
            if r.interpretation_id in seen:
                raise ValueError(
                    f"ModelValidationReport.rejected has duplicate interpretation_id: {r.interpretation_id!r}."
                )
            seen.add(r.interpretation_id)
        return self

    @model_validator(mode="after")
    def _overall_passed_consistent(self) -> "ModelValidationReport":
        if not self.request.spec.fail_on_rejection:
            return self
        if not self.overall_passed and not self.rejected and not self.issues:
            raise ValueError(
                "ModelValidationReport with overall_passed=False and "
                "fail_on_rejection=True must include at least one rejected "
                "interpretation or one common issue."
            )
        return self

    @model_validator(mode="after")
    def _computed_at_is_timezone_aware(self) -> "ModelValidationReport":
        if self.computed_at is not None and self.computed_at.tzinfo is None:
            object.__setattr__(
                self,
                "computed_at",
                self.computed_at.replace(tzinfo=timezone.utc),
            )
        return self
